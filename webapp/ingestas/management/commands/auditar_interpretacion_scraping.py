"""Default is a read-only plan. Applying preserves records, dates and audit trail."""
import json
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from ingestas.models import PropiedadesCompetencia, RevisionPropiedadScraping, CambioPropiedadScraping
from ingestas.interpretation_repair import propose, VERSION

FIELDS = ('id','fuente','tipo_inmueble','tipo_operacion','area_terreno','area_construida',
          'area_m2','precio_usd','url','descripcion','datos_crudos')


class Command(BaseCommand):
    help = 'Audita corrupción histórica de áreas/operación; solo escribe con --apply. No borra anuncios.'

    def add_arguments(self, parser):
        parser.add_argument('--apply',action='store_true')
        parser.add_argument('--fuente',default='')
        parser.add_argument('--ids',nargs='+',type=int)

    def handle(self, *args, **options):
        # Only read full raw documents for candidate defects, not every large
        # scraper payload. This is a targeted repair, not a quality certificate.
        query=PropiedadesCompetencia.objects.filter(
            Q(tipo_inmueble='Casa') & (Q(area_terreno__lt=30) | Q(area_construida__gt=10000) | Q(precio_usd__lt=1000))
            | Q(tipo_operacion='Venta',url__icontains='alquiler')
            | Q(tipo_operacion='Venta',url__icontains='/alcl')
            | Q(tipo_operacion='Alquiler',url__icontains='venta')
            | Q(tipo_operacion='Alquiler',url__icontains='/vecl')
        ).order_by('id')
        if options['fuente']:query=query.filter(fuente=options['fuente'])
        if options['ids']:query=query.filter(id__in=options['ids'])
        last=0;summary={'reviewed':0,'proposals':0,'changed':0,'quarantined':0,'applied':options['apply']}
        while True:
            # Bounded page; do not hold a SQL Server result cursor while writing.
            rows=list(query.filter(id__gt=last).values(*FIELDS)[:200])
            if not rows:break
            last=rows[-1]['id']
            reviews={r.propiedad_id:r for r in RevisionPropiedadScraping.objects.filter(propiedad_id__in=[r['id'] for r in rows])}
            for row in rows:
                summary['reviewed']+=1
                review=reviews.get(row['id'])
                plan=propose(row,review.campos_protegidos if review else (),review.correcta if review else False)
                if not plan['changes'] and not plan['quarantine']:continue
                if not options['apply']:
                    summary['proposals']+=1
                    self.stdout.write(json.dumps(plan,ensure_ascii=False,default=str))
                    continue
                with transaction.atomic():
                    row=PropiedadesCompetencia.objects.select_for_update().values(*FIELDS).get(pk=row['id'])
                    review=RevisionPropiedadScraping.objects.filter(propiedad_id=row['id']).first()
                    plan=propose(row,review.campos_protegidos if review else (),review.correcta if review else False)
                    if not plan['changes'] and not plan['quarantine']:continue
                    summary['proposals']+=1
                    self.stdout.write(json.dumps(plan,ensure_ascii=False,default=str))
                    changes={key:{'before':value['before'],'after':value['after']} for key,value in plan['changes'].items()}
                    updates={key:value['after'] for key,value in plan['changes'].items()}
                    if updates:
                        PropiedadesCompetencia.objects.filter(pk=row['id']).update(**updates)
                        summary['changed']+=1
                    if plan['quarantine']:
                        if review is None:review=RevisionPropiedadScraping(propiedad_id=row['id'])
                        reason=VERSION+': '+'; '.join(plan['quarantine'])
                        if not review.excluida:
                            changes['excluida']={'before':False,'after':True}
                            old_reason=review.motivo
                            review.excluida=True
                            review.motivo=(old_reason+'\n' if old_reason else '')+reason
                            changes['motivo']={'before':old_reason,'after':review.motivo}
                            review.save()
                            summary['quarantined']+=1
                    if changes:
                        # JSON contains before/after values for later human review.
                        serial=json.loads(json.dumps(changes,default=lambda x:float(x) if isinstance(x,Decimal) else str(x)))
                        CambioPropiedadScraping.objects.create(propiedad_id=row['id'],usuario='system:'+VERSION,cambios=serial)
        self.stdout.write(json.dumps(summary,ensure_ascii=False))
