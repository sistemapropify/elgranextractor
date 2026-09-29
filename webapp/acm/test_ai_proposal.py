import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from django.core.cache import cache
from acm.components_ai import propose_result
from acm.components_engine import calculate
from acm.test_weighted_adjustments import fixture


class ProposalTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.p,self.rows=fixture()
        self.result=calculate(self.rows,self.p)

    def invoke(self,body):
        api=Mock(return_value=(True,'OK',{'content':json.dumps(body)}))
        service=SimpleNamespace(LLMService=SimpleNamespace(_call_deepseek_api=api))
        with patch.dict(sys.modules,{'intelligence.services.llm':service}):
            result=propose_result('user',self.p,self.rows,self.result,[])
        return result,api

    def test_real_ids_and_brief_explanation_are_validated_and_cached(self):
        self.rows[0].update(description='private text',phone='private phone',title='private name')
        result,api=self.invoke({'ids':['a'],'justificacion':'Es la casa más parecida en ambas superficies.'})
        self.assertEqual(result['ids'],['a'])
        self.assertFalse(api.call_args.kwargs['thinking'])
        payload=api.call_args.kwargs['messages'][0]['content']
        self.assertNotIn('private',payload)
        self.assertNotIn('lat',json.loads(payload)['candidatos'][0])
        result,api=self.invoke({'ids':['invented'],'justificacion':'no usar'})
        self.assertEqual(result['ids'],['a'])
        api.assert_not_called()

    def test_rejects_unknown_duplicate_or_ineligible_ids(self):
        for ids in [['invented'],['land'],['a','a'],[],['a']*4]:
            with self.subTest(ids=ids),self.assertRaises(RuntimeError):
                self.invoke({'ids':ids,'justificacion':'Texto'})

    def test_invalid_proposal_does_not_change_result(self):
        before=json.dumps(self.result,sort_keys=True)
        with self.assertRaises(RuntimeError):self.invoke({'ids':['a'],'justificacion':None})
        self.assertEqual(before,json.dumps(self.result,sort_keys=True))
