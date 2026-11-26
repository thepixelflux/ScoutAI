"""A bounded tool-calling loop. Responses are assembled from tool results, never invented."""
import json
import logging
import re
import httpx
from .config import settings
from .schemas import SearchRequest
from .retrieval import search
from .models import Opportunity
log = logging.getLogger(__name__)
TOOLS = [
 {'type':'function','function':{'name':'search_opportunities','description':'Search opportunity listings using the user request.','parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'get_opportunity_details','description':'Get one opportunity by its numeric id.','parameters':{'type':'object','properties':{'opportunity_id':{'type':'integer'}},'required':['opportunity_id'],'additionalProperties':False}}},
]

def execute_tool(db, name, args):
    if name == 'search_opportunities':
        return search(db, SearchRequest(query=args.get('query',''), limit=5)).model_dump(mode='json')
    if name == 'get_opportunity_details':
        o = db.get(Opportunity, int(args['opportunity_id']))
        if not o: return {'error':'Opportunity not found'}
        return {'id':o.id,'title':o.title,'organization':o.organization,'description':o.description,'location':o.location,'remote':o.remote,'source_type':o.source_type,'source_url':o.source_url,'skills':[s.name for s in o.skills]}
    raise ValueError('Unknown tool')

def run_agent(db, message):
    tool_name = 'search_opportunities'
    args = {'query': message}
    mode = 'fallback'
    if settings.llm_api_key:
        try:
            r = httpx.post(settings.llm_base_url.rstrip('/') + '/chat/completions', headers={'Authorization':'Bearer '+settings.llm_api_key}, json={'model':settings.llm_model,'messages':[{'role':'system','content':'Select the appropriate tool. Use details only when the user supplies a specific opportunity ID.'},{'role':'user','content':message}],'tools':TOOLS,'tool_choice':'required'}, timeout=15)
            r.raise_for_status()
            call = r.json()['choices'][0]['message']['tool_calls'][0]['function']
            if call['name'] not in ('search_opportunities','get_opportunity_details'): raise ValueError('Invalid tool')
            tool_name, args, mode = call['name'], json.loads(call['arguments']), 'llm'
        except Exception:
            log.warning('Agent provider unavailable; using fallback', exc_info=True)
    if mode == 'fallback':
        match = re.search(r'\b(?:id|opportunity)\s*#?\s*(\d+)\b', message, re.I)
        if match: tool_name, args = 'get_opportunity_details', {'opportunity_id':int(match.group(1))}
    try: data = execute_tool(db, tool_name, args)
    except (ValueError, KeyError, TypeError):
        tool_name, mode = 'search_opportunities', 'fallback'
        data = execute_tool(db, tool_name, {'query':message})
    # The client receives retrieved data rather than an unconstrained generated answer.
    return {'tool':tool_name, 'mode':mode, 'data':data}
