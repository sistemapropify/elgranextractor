import csv
import hmac
import json
from collections import defaultdict
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import RemarketingCampaign, RemarketingDelivery
from .remarketing_engine import CONFIRMED, LIMA, eligibility, policy_for, record_result
from .remarketing_forms import CampaignForm, CampaignSteps, render_message
from .remarketing_gateway import config, crm_snapshot, gateway_ready


def management_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if getattr(getattr(request, 'user', None), 'is_superuser', False):
            return view(request, *args, **kwargs)
        # Reuse the established CRM authorization, including external profiles.
        from .views import management_access_required
        return management_access_required(view)(request, *args, **kwargs)
    return wrapped


def report_rows(deliveries, granularity='day'):
    rows = defaultdict(lambda: dict(messages=0, sent=0, delivered=0, responses=0, failed=0, pending=0, accepted=0, uncertain=0, skipped=0, contacts=set(), matured=0, matured_responses=0))
    now = timezone.now()
    for item in deliveries:
        moment = (item.sent_at or item.attempted_at or item.due_at).astimezone(LIMA)
        if granularity == 'hour':
            key = moment.strftime('%Y-%m-%d %H:00')
        elif granularity == 'week':
            key = (moment-timedelta(days=moment.weekday())).strftime('%Y-%m-%d')
        elif granularity == 'month':
            key = moment.strftime('%Y-%m')
        else:
            key = moment.strftime('%Y-%m-%d')
        row = rows[key]
        row['messages'] += 1
        if item.status in CONFIRMED:
            row['sent'] += 1
            row['contacts'].add(item.enrollment.contact_key)
            if item.sent_at and item.sent_at <= now-timedelta(hours=24):
                row['matured'] += 1
                row['matured_responses'] += bool(item.response_at)
        row['delivered'] += item.status == 'delivered'
        row['responses'] += bool(item.response_at)
        row['failed'] += item.status == 'failed'
        row['pending'] += item.status == 'pending'
        row['accepted'] += item.status == 'accepted'
        row['uncertain'] += item.status in ('sending', 'uncertain')
        row['skipped'] += item.status in ('skipped', 'cancelled')
    return [dict(period=period, **{**row, 'contacts': len(row['contacts'])}, rate=round(100*row['responses']/row['sent'], 1) if row['sent'] else None, mature_rate=round(100*row['matured_responses']/row['matured'], 1) if row['matured'] else None) for period, row in sorted(rows.items(), reverse=True)]


@management_only
@require_GET
def campaigns(request):
    return render(request, 'lead_intelligence/remarketing_campaigns.html', {'campaigns': RemarketingCampaign.objects.prefetch_related('steps'), 'gateway_ready': gateway_ready()})


@management_only
@require_http_methods(['GET', 'POST'])
def campaign_edit(request, campaign_id=None):
    campaign = get_object_or_404(RemarketingCampaign, pk=campaign_id) if campaign_id else RemarketingCampaign()
    editable = not campaign.pk or not campaign.enrollments.exists()
    form = CampaignForm(request.POST or None, instance=campaign)
    initial = [{'title': f'Seguimiento {i}', 'delay_minutes': delay, 'body': ''} for i, delay in enumerate((120, 240, 360), 1)] if not campaign.pk else None
    steps = CampaignSteps(request.POST or None, instance=campaign, prefix='steps', initial=initial)
    # initial forms require extra forms; default on existing campaigns remains zero.
    if not campaign.pk and request.method == 'GET':
        steps.extra = 3
    if request.method == 'POST':
        if not editable:
            return HttpResponse('La campaña tiene inscripciones. Duplícala para conservar el historial.', status=409)
        form_valid = form.is_valid()
        steps_valid = steps.is_valid()
        if form_valid and steps_valid:
            with transaction.atomic():
                if campaign.pk:
                    locked = RemarketingCampaign.objects.select_for_update().get(pk=campaign.pk)
                    if locked.enrollments.exists() or locked.status == 'active':
                        return HttpResponse('Pausa la campaña y duplica si tiene historial.', status=409)
                campaign = form.save(commit=False)
                campaign.revision += int(bool(campaign.pk))
                campaign.save()
                # No enrollments exist: rebuild editable steps to allow swapping
                # delays without hitting a transient unique constraint violation.
                from .models import RemarketingStep
                step_values = [{key: item.cleaned_data[key] for key in ('title', 'delay_minutes', 'body')} for item in steps.forms if item.cleaned_data and not item.cleaned_data.get('DELETE')]
                campaign.steps.all().delete()
                RemarketingStep.objects.bulk_create([RemarketingStep(campaign=campaign, **values) for values in step_values])
            messages.success(request, 'Campaña guardada. No se enviaron mensajes.')
            return redirect('analisis_crm:remarketing_campaign_edit', campaign_id=campaign.pk)
    preview = None
    lead_raw = request.GET.get('lead_id', '')
    if campaign.pk and lead_raw:
        try:
            snapshot = crm_snapshot(int(lead_raw))
            info, reason = eligibility(policy_for(campaign), snapshot, timezone.now())
            preview = {'reason': reason, 'steps': []}
            if info:
                for step in campaign.steps.all():
                    due = info['anchor'] + timedelta(minutes=step.delay_minutes)
                    preview['steps'].append({'title': step.title, 'due': due.astimezone(LIMA), 'body': render_message(step.body, snapshot), 'fits': due < info['expiry']})
        except Exception:
            preview = {'reason': 'No se pudo verificar el lead o completar las variables.', 'steps': []}
    return render(request, 'lead_intelligence/remarketing_campaign_edit.html', {'campaign': campaign, 'form': form, 'steps': steps, 'editable': editable and campaign.status != 'active', 'preview': preview, 'gateway_ready': gateway_ready()})


@management_only
@require_POST
def campaign_action(request, campaign_id):
    with transaction.atomic():
        campaign = get_object_or_404(RemarketingCampaign.objects.select_for_update(), pk=campaign_id)
        action = request.POST.get('action')
        if action == 'duplicate':
            copied_steps = list(campaign.steps.all())
            values = {field: getattr(campaign, field) for field in policy_for(campaign)}
            copied = RemarketingCampaign.objects.create(name=f'{campaign.name[:145]} (copia)', **values)
            for step in copied_steps:
                step.pk, step.campaign = None, copied
                step.save()
            return redirect('analisis_crm:remarketing_campaign_edit', campaign_id=copied.pk)
        if action == 'activate':
            data = {field: value for field, value in policy_for(campaign).items()}
            for field in ('allowed_statuses', 'allowed_channels', 'agent_ids'):
                data[field] = ','.join(map(str, data[field]))
            data['name'] = campaign.name
            validator = CampaignForm(data, instance=campaign)
            if not validator.is_valid() or not campaign.steps.exists():
                return HttpResponse('Completa las condiciones, horarios y plantillas antes de activar.', status=400)
            from .remarketing_forms import StepForm
            configured_steps = list(campaign.steps.all())
            if any(not StepForm({'title': step.title, 'body': step.body, 'delay_minutes': step.delay_minutes}).is_valid() for step in configured_steps):
                return HttpResponse('Hay plantillas inválidas.', status=400)
            if any(b.delay_minutes-a.delay_minutes < campaign.min_gap_minutes for a, b in zip(configured_steps, configured_steps[1:])):
                return HttpResponse('Los pasos no respetan la separación mínima.', status=400)
            campaign.status = 'active'
        elif action == 'pause':
            campaign.status = 'paused'
        else:
            return HttpResponse('Acción inválida.', status=400)
        campaign.save(update_fields=['status', 'updated_at'])
    return redirect('analisis_crm:remarketing_campaigns')


@management_only
@require_GET
def deliveries_report(request):
    from datetime import date
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET.get('from') or (today-timedelta(days=13)).isoformat())
        end = date.fromisoformat(request.GET.get('to') or today.isoformat())
        if start > end or (end-start).days > 366:
            raise ValueError
        campaign_id = int(request.GET['campaign']) if request.GET.get('campaign') else None
        step_position = int(request.GET['step']) if request.GET.get('step') else None
    except ValueError:
        return HttpResponse('Período o campaña inválido; máximo 366 días.', status=400)
    granularity = request.GET.get('granularity', 'day')
    if granularity not in ('hour', 'day', 'week', 'month'):
        granularity = 'day'
    from datetime import datetime, time
    from django.db.models.functions import Coalesce
    deliveries = RemarketingDelivery.objects.select_related('enrollment__campaign').annotate(report_at=Coalesce('sent_at', 'attempted_at', 'due_at')).filter(report_at__gte=datetime.combine(start, time.min, tzinfo=LIMA), report_at__lt=datetime.combine(end+timedelta(days=1), time.min, tzinfo=LIMA))
    if campaign_id:
        deliveries = deliveries.filter(enrollment__campaign_id=campaign_id)
    if step_position:
        deliveries = deliveries.filter(position=step_position)
    rows = report_rows(deliveries, granularity)
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="remarketing.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        keys = ['period', 'sent', 'delivered', 'contacts', 'responses', 'rate', 'mature_rate', 'pending', 'accepted', 'failed', 'uncertain', 'skipped']
        writer.writerow(keys)
        for row in rows:
            writer.writerow([row[key] for key in keys])
        return response
    confirmed = deliveries.filter(status__in=CONFIRMED)
    reached = confirmed.values('enrollment_id').distinct().count()
    responded = confirmed.filter(response_at__isnull=False).values('enrollment_id').distinct().count()
    return render(request, 'lead_intelligence/remarketing_deliveries.html', {'rows': rows, 'deliveries': deliveries.order_by('-report_at')[:200], 'campaigns': RemarketingCampaign.objects.all(), 'selected_campaign': campaign_id, 'selected_step': step_position, 'date_from': start, 'date_to': end, 'granularity': granularity, 'reached': reached, 'responded': responded, 'recovery_rate': round(100*responded/reached, 1) if reached else None})


@csrf_exempt
@require_POST
def delivery_receipt(request):
    """Server-to-server, fail closed. Receipts never authorize a new send."""
    expected = config('REMARKETING_RECEIPT_TOKEN')
    if not expected or not hmac.compare_digest(request.headers.get('Authorization', '').encode(), f'Bearer {expected}'.encode()):
        return HttpResponseForbidden()
    try:
        payload = json.loads(request.body)
        delivery = RemarketingDelivery.objects.get(idempotency_key=payload['idempotency_key'])
        record_result(delivery.pk, payload)
    except (ValueError, TypeError, KeyError, ValidationError, RemarketingDelivery.DoesNotExist):
        return JsonResponse({'error': 'Confirmación inválida.'}, status=400)
    return JsonResponse({'status': 'ok'})
