import json
from django.test import SimpleTestCase
from . import test_source_placement
from . import master_layers, source_placement


class BlockPlacementTests(SimpleTestCase):
    def setUp(self):
        test_source_placement.SourcePlacementTests.setUp(self)
        def feature(identity, west, parent=None):
            return {'id': identity, 'type': 'Feature', 'properties': {'ELEMENT_ID': identity, 'BLOCK_REF': parent},
                    'geometry': {'type': 'Polygon', 'coordinates': [[[west,-16.37],[west+.001,-16.37],
                                  [west+.001,-16.369],[west,-16.369],[west,-16.37]]]}}
        for key in ('lotes', 'manzanas'):
            features = [feature('a' if key == 'manzanas' else 'lot-a', -71.55, None if key == 'manzanas' else 'a'),
                        feature('b' if key == 'manzanas' else 'lot-b', -71.54, None if key == 'manzanas' else 'b')]
            (self.folder/(key+'.geojson')).write_text(json.dumps({'type': 'FeatureCollection', 'features': features}), encoding='utf8')

    def test_move_scale_only_selected_block_with_lots_and_global_offset(self):
        originals = {k: (self.folder/(k+'.geojson')).read_bytes() for k in ('lotes','manzanas')}
        before = master_layers.layer(self.source, 'lotes', '040103')['features']
        edit = {'east_m': 1800, 'north_m': 15, 'scale': 1.5}
        value = source_placement.save(self.folder, dict(revision=0,east_m=7,north_m=-4,blocks={'a':edit},locked=True), 'test')
        dx,dy = source_placement.degrees({'east_m':1807,'north_m':11}, -16.365)
        for key in ('lotes','manzanas'):
            features = master_layers.layer(self.source,key,'040103')['features']
            p = features[0]['geometry']['coordinates'][0][0]
            self.assertAlmostEqual(p[0], -71.5495+(-71.55+71.5495)*1.5+dx, places=8)
            self.assertAlmostEqual(p[1], -16.3695+(-16.37+16.3695)*1.5+dy, places=8)
            # The second block receives only the source translation.
            global_dx,global_dy = source_placement.degrees(value,-16.365)
            q = features[1]['geometry']['coordinates'][0][0]
            self.assertAlmostEqual(q[0], before[1]['geometry']['coordinates'][0][0][0]+global_dx, places=8)
            self.assertAlmostEqual(q[1], -16.37+global_dy, places=8)
            self.assertEqual((self.folder/(key+'.geojson')).read_bytes(),originals[key])
        moved = master_layers.layer(self.source,'lotes','040103')['features'][0]['geometry']['coordinates'][0]
        cx,cy = (moved[0][0]+moved[2][0])/2,(moved[0][1]+moved[2][1])/2
        radius = master_layers.radius(self.source,cy,cx,100)
        self.assertEqual([f['id'] for f in radius['lots']['features']], ['lot-a'])
        self.assertEqual([f['id'] for f in radius['blocks']['features']], ['a'])
        self.assertGreater(master_layers.source_metadata(self.source)['bbox'][2], -71.54)
        raw = master_layers.layer(self.source,'lotes','040103',original=True)
        self.assertEqual(raw['features'],before)
        self.assertEqual(raw['placement']['blocks']['a'],edit)
        # Legacy source-wide saves preserve all individual edits.
        again = source_placement.save(self.folder,dict(revision=1,east_m=8,north_m=-3,locked=True),'test')
        self.assertEqual(again['blocks'],value['blocks'])
        self.assertEqual(again['history'][-1]['blocks'],value['blocks'])

    def test_block_validation_and_reset(self):
        for blocks in ([], {'unknown':dict(east_m=0,north_m=0,scale=1)},
                       {'a':dict(east_m=True,north_m=0,scale=1)}, {'a':dict(east_m=0,north_m=0,scale=float('nan'))},
                       {'a':dict(east_m=0,north_m=0,scale=0)}, {'a':dict(east_m=0,north_m=0,scale=10.1)},
                       {'a':dict(east_m=2001,north_m=0,scale=1)}):
            with self.assertRaises(ValueError):
                source_placement.save(self.folder,dict(revision=0,east_m=0,north_m=0,blocks=blocks,locked=True),'test')
        source_placement.save(self.folder,dict(revision=0,east_m=0,north_m=0,blocks={'a':dict(east_m=3,north_m=0,scale=.5)},locked=True),'test')
        source_placement.save(self.folder,dict(revision=1,east_m=0,north_m=0,blocks={},locked=True),'test')
        self.assertEqual(source_placement.read(self.folder)['blocks'],{})
