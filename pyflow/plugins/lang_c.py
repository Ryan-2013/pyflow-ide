"""
PyFlow Language Plugin — C Language (v2)
=========================================
完全重寫，正確識別函式、struct、enum、union、typedef、macro
"""
from __future__ import annotations
import re, os, shutil, subprocess
from plugins import LanguagePlugin, register

_P_INCLUDE   = re.compile(r'^\s*#\s*include\s+[<"]([^>"]+)[>"]')
_P_DEFINE    = re.compile(r'^\s*#\s*define\s+(\w+)(?:\([^)]*\))?\s*(.{0,40})')
_P_STRUCT    = re.compile(r'^\s*(?:typedef\s+)?(?:struct|union|enum)\s+(\w*)\s*\{')
_P_TYPEDEF_FN= re.compile(r'^\s*typedef\s+.+\(\s*\*\s*(\w+)\s*\)')
_P_IF        = re.compile(r'^\s*(?:else\s+)?if\s*\(')
_P_FOR       = re.compile(r'^\s*for\s*\(')
_P_WHILE     = re.compile(r'^\s*while\s*\(')
_P_DO        = re.compile(r'^\s*do\s*[{\s]')
_P_SWITCH    = re.compile(r'^\s*switch\s*\(')
_P_GOTO      = re.compile(r'^\s*goto\s+\w+')
_P_RETURN    = re.compile(r'^\s*return\b')
_P_MALLOC    = re.compile(r'\b(?:malloc|calloc|realloc|alloca)\s*\(')
_P_FREE      = re.compile(r'\bfree\s*\(')
_P_ASSERT    = re.compile(r'\bassert\s*\(')

_C_KW = frozenset({
    'if','else','for','while','do','switch','case','default','break','continue',
    'return','goto','typedef','struct','union','enum','sizeof','typeof',
    'static','extern','register','volatile','const','inline','auto',
    'unsigned','signed','long','short','void','int','char','float','double',
    'bool','_Bool','NULL','true','false',
})

_C_TYPES = frozenset({'int','char','void','float','double','long','short',
                       'unsigned','signed','bool','size_t','FILE','DIR',
                       'uint8_t','uint16_t','uint32_t','uint64_t',
                       'int8_t','int16_t','int32_t','int64_t'})

# Function pattern: optional qualifiers + return type + name + (
_P_FUNC = re.compile(
    r'^(?:static\s+)?(?:inline\s+)?(?:extern\s+)?'
    r'(?:__attribute__\([^)]+\)\s*)?'
    r'(?:const\s+)?(?:volatile\s+)?'
    r'(?:unsigned\s+|signed\s+|long\s+long\s+|long\s+)?'
    r'(?:int|long|short|char|float|double|void|bool|wchar_t|ptrdiff_t|'
    r'size_t|ssize_t|off_t|uint8_t|uint16_t|uint32_t|uint64_t|'
    r'int8_t|int16_t|int32_t|int64_t|intptr_t|uintptr_t|\w+_t|\w+)'
    r'\s*[\*]*\s*'
    r'(\w+)\s*\('
)


def _strip_comments(line: str) -> str:
    in_str = False; esc = False
    for j, c in enumerate(line):
        if esc: esc = False; continue
        if c == '\\' and in_str: esc = True; continue
        if c == '"': in_str = not in_str; continue
        if c == '/' and j+1 < len(line) and line[j+1] == '/' and not in_str:
            return line[:j]
    return line


def parse_c(code: str, path: str) -> dict:
    lines  = code.split('\n')
    flow   = []
    defs   = []
    depth  = 0
    in_bc  = False   # inside block comment

    for i, raw in enumerate(lines, 1):
        # Block comment
        if in_bc:
            if '*/' in raw: in_bc = False
            continue
        if '/*' in raw:
            in_bc = ('*/' not in raw.split('/*', 1)[1])
            cl = raw[:raw.index('/*')]
        else:
            cl = _strip_comments(raw)

        s = cl.strip()
        if not s: continue

        opens  = cl.count('{') - cl.count('\\{')
        closes = cl.count('}') - cl.count('\\}')

        # ── Preprocessor ─────────────────────────────────────────
        if s.startswith('#'):
            m = _P_INCLUDE.match(s)
            if m:
                flow.append({'id':f'inc_{i}','type':'include',
                             'label':f'#include <{m.group(1)}>','line':i,'detail':s,'calls':[]})
            m = _P_DEFINE.match(s)
            if m:
                flow.append({'id':f'mac_{i}','type':'assign',
                             'label':f'#define {m.group(1)}','line':i,'detail':s,'calls':[]})
            depth += opens - closes; continue

        # ── Struct / union / enum ─────────────────────────────────
        if _P_STRUCT.match(s):
            m    = _P_STRUCT.match(s)
            kw   = 'struct' if 'struct' in s[:s.index('{')] else ('union' if 'union' in s[:s.index('{')] else 'enum')
            name = m.group(1)
            # If anonymous, look for typedef name at end of block on same line
            if not name:
                td = re.search(r'\}\s*(\w+)\s*;', s)
                name = td.group(1) if td else f'anon_{kw}_{i}'
            icon = {'struct':'◈','union':'⊕','enum':'⊞'}.get(kw,'◈')
            defs.append({'id':name,'type':'class','label':name,'line':i,
                         'detail':s[:70],'methods':[],'is_async':False,'qualifier_icon':icon})
            depth += opens - closes; continue

        # ── Function pointer typedef ──────────────────────────────
        if _P_TYPEDEF_FN.match(s):
            m = _P_TYPEDEF_FN.match(s)
            defs.append({'id':m.group(1),'type':'function','label':m.group(1),'line':i,
                         'detail':s[:70],'methods':[],'is_async':False,'qualifier_icon':'⊛'})
            depth += opens - closes; continue

        # ── Function definition (only at depth 0) ─────────────────
        if depth == 0 and '(' in s and not s.startswith(('/*','//','*','=')):
            m = _P_FUNC.match(s)
            if m:
                name = m.group(1)
                if name not in _C_KW and name not in _C_TYPES and len(name) > 1:
                    pre   = s[:m.start(1)]
                    quali = ('◎' if 'static' in pre else '') + ('ᵢ' if 'inline' in pre else '')
                    defs.append({'id':name,'type':'function','label':name,'line':i,
                                 'detail':s[:70],'methods':[],'is_async':False,
                                 'qualifier_icon':quali or None})
                    flow.append({'id':f'fn_{name}_{i}','type':'call',
                                 'label':name+'()','line':i,'detail':'','calls':[name]})

        # ── Flow nodes ────────────────────────────────────────────
        if _P_IF.match(s):
            flow.append({'id':f'if_{i}','type':'condition','label':s[:60],'line':i,'detail':'','calls':[]})
        elif _P_FOR.match(s):
            flow.append({'id':f'for_{i}','type':'loop','label':s[:60],'line':i,'detail':'','calls':[]})
        elif _P_WHILE.match(s):
            flow.append({'id':f'wh_{i}','type':'loop','label':s[:55],'line':i,'detail':'','calls':[]})
        elif _P_DO.match(s):
            flow.append({'id':f'do_{i}','type':'loop','label':'do { … } while','line':i,'detail':'','calls':[]})
        elif _P_SWITCH.match(s):
            flow.append({'id':f'sw_{i}','type':'match','label':s[:55],'line':i,'detail':'','calls':[]})
        elif _P_GOTO.match(s):
            flow.append({'id':f'gt_{i}','type':'flow_ctrl','label':s[:50],'line':i,'detail':'','calls':[]})
        elif _P_RETURN.match(s) and depth <= 2:
            flow.append({'id':f'ret_{i}','type':'flow_ctrl','label':s[:55],'line':i,'detail':'','calls':[]})
        elif _P_MALLOC.search(s):
            flow.append({'id':f'mal_{i}','type':'malloc','label':s[:60],'line':i,'detail':'heap alloc','calls':[]})
        elif _P_FREE.search(s):
            flow.append({'id':f'fr_{i}','type':'malloc','label':s[:55],'line':i,'detail':'heap free','calls':[]})
        elif _P_ASSERT.search(s):
            flow.append({'id':f'as_{i}','type':'exception','label':s[:55],'line':i,'detail':'','calls':[]})

        depth += opens - closes

    return {'flow':flow,'definitions':defs,'error':None,'error_line':0}


class CPlugin(LanguagePlugin):
    id='c'; name='C'; version='2.0.0'
    extensions=['.c','.h']; monaco_id='c'; icon='🅒'; color='#555599'
    description='C — functions, structs, enums, macros, pointer/malloc visualization'

    def parse(self,code,path):         return parse_c(code,path)
    def extract_symbols(self,code,path,parse_result=None):
        r = parse_result or self.parse(code,path)
        return [{'name':d['id'],'kind':d['type'],'line':d['line'],'sig':d.get('detail','')[:80],
                 'doc':'','source':'user','module':'','parent':''} for d in r.get('definitions',[])]
    def format_code(self,code):
        if shutil.which('clang-format'):
            r=subprocess.run(['clang-format','--style=llvm','--assume-filename=a.c'],
                             input=code,capture_output=True,text=True,timeout=10)
            return {'formatted':r.stdout if r.returncode==0 else code,'error':r.stderr.strip() or None,'tool':'clang-format'}
        return None
    def get_lsp_command(self):
        return ['clangd'] if shutil.which('clangd') else None
    def get_run_command(self,path):
        for cc in ['gcc','clang','cc']:
            if shutil.which(cc):
                return ['sh','-c',f'{cc} -O2 -Wall -o /tmp/_pyflow_c "{path}" && /tmp/_pyflow_c']
        return None
    def get_node_types(self):
        return {'include':{'n':'#include','c':'#1a1a2a'},'malloc':{'n':'heap','c':'#2a1a0a'}}

register(CPlugin())
