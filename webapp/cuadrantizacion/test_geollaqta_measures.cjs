const assert=require('node:assert/strict');
const {fixture,flush}=require('./test_geollaqta_gallery.cjs');
function value(f,label){
    const row=f.descendants(f.element('geollaqta-detail'),'div').find(e=>e.className==='geollaqta-field' && e.children[0].textContent===label);
    assert.ok(row,'Missing field '+label);return row.children[1].textContent;
}
async function main(){
    for(const browser of [true,false]){
        const f=await fixture(browser);
        assert.equal(value(f,'Área de terreno (m²)'),'200','Report overrides vector 999');
        assert.equal(value(f,'Área construida (m²)'),'20.5','Report overrides vector 2012');
        for(const [side,metres] of [['Frente','10'],['Derecha','20'],['Izquierda','20'],['Fondo','10']])assert.equal(value(f,side+' (m)'),metres);
        assert.equal(f.element('geollaqta-detail').children.some(e=>String(e.textContent).includes('Fuente:')),false);
    }
    const pending=await fixture(true,{deferReport:true});
    assert.equal(value(pending,'Área construida (m²)'),'Cargando…','Unverified vector area is never flashed');
    await pending.choose('04012607042018');await flush();
    pending.pendingReports[0].resolve();await flush();
    assert.equal(value(pending,'Área construida (m²)'),'Cargando…','Stale report cannot fill another lot');
    pending.pendingReports[1].resolve({land_area:'300',built_area:'31.7',boundaries:{frente:'15'}});await flush();
    assert.equal(value(pending,'Área construida (m²)'),'31.7');
    const denied=await fixture(true,{failReport:true});
    assert.equal(value(denied,'Área construida (m²)'),'Sin dato verificado','Errors never fall back to vector 2012');
    const wrong=await fixture(true,{wrongLot:true});
    assert.equal(value(wrong,'Área de terreno (m²)'),'Sin dato verificado');
    const multiple=await fixture(true,{multiple:true});
    const selector=multiple.descendants(multiple.element('geollaqta-detail'),'select')[0];
    assert.equal(value(multiple,'Área construida (m²)'),'20.5');
    selector.value='0401262013010431545';await selector.events.change();await flush();
    assert.equal(value(multiple,'Área construida (m²)'),'42.35','Different unit areas are not summed');
    console.log('Report areas, four boundaries, loading, failed reads, wrong lot, stale selection and separate units passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
