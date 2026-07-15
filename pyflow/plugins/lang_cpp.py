"""
PyFlow Language Plugin — C++ (v2)
====================================
在 C parser 基礎上新增：
- class / template class / template function
- lambda（[capture](params) → body）
- namespace
- constructor / destructor / operator overload
- std:: smart pointer、range-for、structured binding
- C++20 concepts / requires
- 建構子初始化列表識別
"""
from __future__ import annotations
import re, os, shutil, subprocess
from plugins import LanguagePlugin, register
from plugins.lang_c import parse_c, _strip_comments, _P_IF, _P_FOR, _P_WHILE, _P_SWITCH, _P_RETURN

# ── C++ specific patterns ─────────────────────────────────────────
_P_CLASS     = re.compile(r'^\s*(?:template\s*<[^>]*>\s*)?(?:class|struct)\s+(\w+)(?:\s*:\s*.*?)?\s*\{')
_P_TEMPLATE  = re.compile(r'^\s*template\s*<')
_P_NAMESPACE = re.compile(r'^\s*namespace\s+(\w+|\w+::\w+)\s*\{')
_P_LAMBDA    = re.compile(r'\[(?:[&=]|[a-zA-Z_]\w*)*\]\s*(?:<[^>]*>\s*)?\([^)]*\)\s*(?:->.*?)?\s*\{')
_P_USING     = re.compile(r'^\s*using\s+(?:namespace\s+)?(\w[\w:]*)\s*;')
_P_SMART_PTR = re.compile(r'\b(?:unique_ptr|shared_ptr|weak_ptr|make_unique|make_shared)\s*[<(]')
_P_RANGE_FOR = re.compile(r'^\s*for\s*\(\s*(?:auto|const)\s*(?:&|&&)?\s*\w+\s*:\s*')
_P_STRUCT_BIND=re.compile(r'^\s*auto\s*\[\s*\w+')
_P_CONCEPT   = re.compile(r'^\s*(?:requires|concept)\s+\w+')
_P_OPERATOR  = re.compile(r'\boperator\s*(?:[\+\-\*\/\%\&\|\^~!<>=\[\]]|<<|>>|==|!=|<=|>=|\(\)|\[\]|\+\+|--)')
_P_TRY       = re.compile(r'^\s*try\s*\{')
_P_CATCH     = re.compile(r'^\s*catch\s*\(')
_P_THROW     = re.compile(r'^\s*throw\b')
_P_MOVE      = re.compile(r'\bstd::move\s*\(')
_P_COROUTINE = re.compile(r'\b(?:co_await|co_yield|co_return)\b')

_CPP_KW = frozenset({
    'if','else','for','while','do','switch','case','default','break','continue',
    'return','goto','typedef','struct','union','enum','sizeof','typeof','namespace',
    'class','public','private','protected','virtual','override','final',
    'template','typename','static','extern','inline','const','constexpr',
    'volatile','auto','decltype','nullptr','true','false','this','new','delete',
    'operator','friend','explicit','mutable','static_assert','requires','concept',
    'co_await','co_yield','co_return','export','import','module',
})


def parse_cpp(code: str, path: str) -> dict:
    lines = code.split('\n')
    flow  = []
    defs  = []
    depth = 0
    in_bc = False

    # Stack: {'type':'class'|'ns'|'fn', 'name':str, 'depth':int, 'def':dict|None}
    scopes: list[dict] = []

    for i, raw in enumerate(lines, 1):
        if in_bc:
            if '*/' in raw: in_bc = False
            continue
        if '/*' in raw:
            in_bc = ('*/' not in raw.split('/*',1)[1])
            cl = raw[:raw.index('/*')]
        else:
            cl = _strip_comments(raw)

        s = cl.strip()
        if not s: continue

        opens  = cl.count('{') - cl.count('\\{')
        closes = cl.count('}') - cl.count('\\}')
        new_d  = depth + opens - closes

        # Pop closed scopes
        while scopes and scopes[-1]['depth'] > new_d:
            scopes.pop()

        top   = scopes[-1] if scopes else None
        in_cls = top and top['type'] in ('class','struct')

        # ── Preprocessor ─────────────────────────────────────────
        if s.startswith('#'):
            if '#include' in s:
                hdr = re.search(r'[<"]([^>"]+)[>"]', s)
                if hdr:
                    flow.append({'id':f'inc_{i}','type':'include',
                                 'label':f'#include <{hdr.group(1)}>','line':i,'detail':s,'calls':[]})
            depth = new_d; continue

        # ── Using / namespace alias ───────────────────────────────
        if _P_USING.match(s):
            m = _P_USING.match(s)
            flow.append({'id':f'us_{i}','type':'import','label':f'using {m.group(1)}',
                         'line':i,'detail':s,'calls':[]})
            depth = new_d; continue

        # ── Namespace ─────────────────────────────────────────────
        if _P_NAMESPACE.match(s):
            m = _P_NAMESPACE.match(s)
            ns_def = {'id':m.group(1),'type':'class','label':m.group(1),'line':i,
                      'detail':s[:70],'methods':[],'is_async':False,'qualifier_icon':'⊡'}
            defs.append(ns_def)
            if opens > 0:
                scopes.append({'type':'ns','name':m.group(1),'depth':new_d,'def':ns_def})
            depth = new_d; continue

        # ── Class / struct declaration ─────────────────────────────
        if _P_CLASS.match(s) and depth <= (1 if scopes else 0) + 2:
            m = _P_CLASS.match(s)
            cname = m.group(1)
            kw    = 'class' if 'class' in s[:s.index(cname)] else 'struct'
            is_template = bool(_P_TEMPLATE.match(s))
            cls_def = {'id':cname,'type':'class','label':cname,'line':i,
                       'detail':s[:80],'methods':[],'is_async':False,
                       'qualifier_icon':'⊞' if is_template else None}
            defs.append(cls_def)
            if opens > 0:
                scopes.append({'type':'class','name':cname,'depth':new_d,'def':cls_def})
            depth = new_d; continue

        # ── Methods inside a class ────────────────────────────────
        if in_cls and top and depth == top['depth']:
            # Look for method signatures
            method_m = re.match(
                r'^\s*(?:virtual\s+)?(?:static\s+)?(?:explicit\s+)?(?:inline\s+)?(?:const\s+)?'
                r'(?:~?(?:unsigned\s+)?(?:\w[\w:]*\s*\*{0,2}\s+))?'
                r'(~?\w+)\s*\(',
                s
            )
            if method_m:
                mname = method_m.group(1)
                if mname not in _CPP_KW and len(mname) > 1:
                    is_virtual  = 'virtual'  in s[:method_m.start(1)]
                    is_static   = 'static'   in s[:method_m.start(1)]
                    is_dtor     = mname.startswith('~')
                    is_ctor     = (mname == top['name'])
                    is_op       = bool(_P_OPERATOR.search(s[:method_m.start(1)+20]))
                    icon = ('◎' if is_static else
                            ('▽' if is_dtor else
                             ('⊕' if is_ctor else
                              ('▲' if is_virtual else
                               ('⊗' if is_op else None)))))
                    if top['def']:
                        top['def']['methods'].append({'id':top['name']+'.'+mname,
                                                       'label':mname,'line':i,'is_async':False,
                                                       'qualifier_icon':icon})
                    if opens > 0:
                        scopes.append({'type':'fn','name':mname,'depth':new_d,'def':None})
                    depth = new_d; continue

        # ── Operator overload (free function) ───────────────────
        if not in_cls and depth <= 1 and 'operator' in s:
            op_m = re.match(
                r'^(?:template\s*<[^>]*>\s*)?(?:inline\s+)?(?:constexpr\s+)?'
                r'(?:std::\w[\w:]*\s*|(?:\w[\w:]*)\s*[*&]*\s+)'
                r'(operator\s*[^\(]+)\s*\(',
                s
            )
            if op_m:
                oname = op_m.group(1).strip().replace(' ','_')
                defs.append({'id':oname,'type':'function','label':op_m.group(1).strip(),
                             'line':i,'detail':s[:80],'methods':[],'is_async':False,'qualifier_icon':'⊗'})
                flow.append({'id':f'op_{i}','type':'call','label':op_m.group(1).strip()+'()','line':i,'detail':'operator','calls':[]})
                if opens > 0:
                    scopes.append({'type':'fn','name':oname,'depth':new_d,'def':None})
                depth = new_d; continue

        # ── Free function (not inside class) ─────────────────────
        if not in_cls and depth <= 1 and '(' in s:
            fn_m = re.match(
                r'^(?:template\s*<[^>]*>\s*)?'
                r'(?:static\s+)?(?:inline\s+)?(?:constexpr\s+)?(?:auto\s+)?'
                r'(?:const\s+)?(?:virtual\s+)?'
                r'(?:std::\w[\w:]*|(?:unsigned\s+)?(?:\w[\w:]*)\s*\*{0,3}\s+)'
                r'(\w+)\s*\(',
                s
            )
            if fn_m:
                fname = fn_m.group(1)
                if fname not in _CPP_KW and len(fname) > 1:
                    is_op = bool(_P_OPERATOR.search(s[:fn_m.start(1)+20]))
                    icon  = ('⊗' if is_op else None)
                    defs.append({'id':fname,'type':'function','label':fname,'line':i,
                                 'detail':s[:80],'methods':[],'is_async':False,'qualifier_icon':icon})
                    flow.append({'id':f'fn_{fname}_{i}','type':'call',
                                 'label':fname+'()','line':i,'detail':'','calls':[fname]})
                    if opens > 0:
                        scopes.append({'type':'fn','name':fname,'depth':new_d,'def':None})
                    depth = new_d; continue

        # ── Flow nodes ────────────────────────────────────────────
        if _P_RANGE_FOR.match(s):
            m2 = re.match(r'for\s*\(\s*(?:auto|const)[^:]+:\s*(\w+)', s.strip())
            label = f'for ({m2.group(1)})' if m2 else 'range-for'
            flow.append({'id':f'rf_{i}','type':'loop','label':label,'line':i,'detail':'range-for','calls':[]})
        elif _P_FOR.match(s):
            flow.append({'id':f'for_{i}','type':'loop','label':s[:55],'line':i,'detail':'','calls':[]})
        elif _P_IF.match(s):
            flow.append({'id':f'if_{i}','type':'condition','label':s[:60],'line':i,'detail':'','calls':[]})
        elif _P_WHILE.match(s):
            flow.append({'id':f'wh_{i}','type':'loop','label':s[:55],'line':i,'detail':'','calls':[]})
        elif _P_SWITCH.match(s):
            flow.append({'id':f'sw_{i}','type':'match','label':s[:55],'line':i,'detail':'','calls':[]})
        elif _P_TRY.match(s):
            flow.append({'id':f'try_{i}','type':'exception','label':'try','line':i,'detail':'','calls':[]})
        elif _P_CATCH.match(s):
            m2 = re.search(r'catch\s*\((.+?)\)', s)
            flow.append({'id':f'cat_{i}','type':'exception',
                         'label':f'catch ({m2.group(1).strip() if m2 else "..."})','line':i,'detail':'','calls':[]})
        elif _P_THROW.match(s):
            flow.append({'id':f'thr_{i}','type':'exception','label':s[:55],'line':i,'detail':'','calls':[]})
        elif _P_RETURN.match(s) and depth <= 3:
            flow.append({'id':f'ret_{i}','type':'flow_ctrl','label':s[:55],'line':i,'detail':'','calls':[]})
        elif _P_LAMBDA.search(s):
            flow.append({'id':f'lmb_{i}','type':'context','label':s[:60],'line':i,'detail':'lambda','calls':[]})
        elif _P_STRUCT_BIND.match(s):
            flow.append({'id':f'sb_{i}','type':'assign','label':s[:60],'line':i,'detail':'structured binding','calls':[]})
        elif _P_SMART_PTR.search(s):
            flow.append({'id':f'sp_{i}','type':'call','label':s[:60],'line':i,'detail':'smart ptr','calls':[]})
        elif _P_COROUTINE.search(s):
            flow.append({'id':f'co_{i}','type':'context','label':s[:55],'line':i,'detail':'coroutine','calls':[],'is_async':True})
        elif _P_CONCEPT.match(s):
            flow.append({'id':f'cpt_{i}','type':'condition','label':s[:55],'line':i,'detail':'concept/requires','calls':[]})

        depth = new_d

    return {'flow':flow,'definitions':defs,'error':None,'error_line':0}


class CppPlugin(LanguagePlugin):
    id='cpp'; name='C++'; version='2.0.0'
    extensions=['.cpp','.cxx','.cc','.hpp','.hxx','.hh','.inl']
    monaco_id='cpp'; icon='🔷'; color='#00599C'
    description='C++ — class/template/lambda/namespace/smart ptr/coroutine/concepts'

    def parse(self,code,path):         return parse_cpp(code,path)
    def extract_symbols(self,code,path,parse_result=None):
        r = parse_result or self.parse(code,path)
        syms=[]
        for d in r.get('definitions',[]):
            syms.append({'name':d['id'],'kind':d['type'],'line':d['line'],'sig':d.get('detail','')[:80],
                         'doc':'','source':'user','module':'','parent':''})
            for m in d.get('methods',[]):
                syms.append({'name':m['label'],'kind':'method','line':m['line'],'sig':d['id']+'.'+m['label']+'()',
                             'doc':'','source':'user','module':d['id'],'parent':d['id']})
        return syms
    def format_code(self,code):
        if shutil.which('clang-format'):
            r=subprocess.run(['clang-format','--style=llvm','--assume-filename=a.cpp'],
                             input=code,capture_output=True,text=True,timeout=10)
            return {'formatted':r.stdout if r.returncode==0 else code,'error':r.stderr.strip() or None,'tool':'clang-format'}
        return None
    def get_lsp_command(self):
        return ['clangd'] if shutil.which('clangd') else None
    def get_run_command(self,path):
        for cc in ['g++','clang++','c++']:
            if shutil.which(cc):
                return ['sh','-c',f'{cc} -std=c++20 -O2 -Wall -o /tmp/_pyflow_cpp "{path}" && /tmp/_pyflow_cpp']
        return None
    def get_node_types(self):
        return {
            'lambda':   {'n':'lambda','c':'#1a1a2a'},
            'context':  {'n':'coroutine','c':'#1a2a1a'},
        }

register(CppPlugin())
