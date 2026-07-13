#!/usr/bin/env python3
"""
PyFlow IDE Theme Builder
========================
將 JSON 主題設定檔編譯為可用的 CSS + JavaScript。

使用方式：
  python tools/build_theme.py themes/my-theme.json              # 編譯並印出
  python tools/build_theme.py themes/my-theme.json --validate   # 只驗證
  python tools/build_theme.py themes/my-theme.json --output css # 只輸出 CSS
  python tools/build_theme.py themes/my-theme.json --output js  # 只輸出 JS
  python tools/build_theme.py themes/my-theme.json --report     # 詳細報告（含對比度）
  python tools/build_theme.py themes/my-theme.json --apply      # 自動套用到 index.html

  python tools/build_theme.py --list                             # 列出所有主題
  python tools/build_theme.py --list-ids                        # 只列出 id
"""
from __future__ import annotations
import argparse, json, math, re, sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent.parent / 'pyflow'
THEMES_DIR = ROOT / 'themes'
INDEX_HTML = ROOT / 'static' / 'index.html'

# ── Required fields & defaults ───────────────────────────────────
REQUIRED_COLORS = [
    'bg','bg2','bg3','bg4','bg5',
    'bd','bd2','bd3',
    'tx','tx2','tx3','tx4',
    'acc','acc2','acc3','sel','ya',
]
NODE_TYPES = [
    'import','assign','call','goroutine','channel',
    'match','condition','loop','context','exception',
    'flow_ctrl','function','class','unsafe_block',
    'error_check','defer','select','other',
]
REQUIRED_NODE_FIELDS = ['bg','text','header']

# Dark theme defaults (used for inheritance)
DARK_DEFAULTS: dict = {
    'colors': {'bg':'#000000','bg2':'#080808','bg3':'#111111','bg4':'#161616','bg5':'#1a1a1a','bd':'#141414','bd2':'#1e1e1e','bd3':'#2a2a2a','tx':'#c8c8c8','tx2':'#3a3a3a','tx3':'#e0e0e0','tx4':'#555555','acc':'#3b82f6','acc2':'#1d4ed8','acc3':'#60a5fa','sel':'#0f1e35','ya':'#ffd43b'},
    'nodes': {'import':{'bg':'#1e3a5f','text':'#93c5fd','header':'#1e3a5f'},'assign':{'bg':'#1a3a2a','text':'#86efac','header':'#1a3a2a'},'call':{'bg':'#2a1a3a','text':'#c4b5fd','header':'#2a1a3a'},'goroutine':{'bg':'#1a3a1a','text':'#4ade80','header':'#1a3a1a'},'channel':{'bg':'#0a2a2a','text':'#2dd4bf','header':'#0a2a2a'},'match':{'bg':'#3a2a1a','text':'#fdba74','header':'#3a2a1a'},'condition':{'bg':'#3a2a1a','text':'#fdba74','header':'#3a2a1a'},'loop':{'bg':'#1a2a3a','text':'#7dd3fc','header':'#1a2a3a'},'context':{'bg':'#2a2a0a','text':'#fde047','header':'#2a2a0a'},'exception':{'bg':'#3a1a1a','text':'#fca5a5','header':'#3a1a1a'},'flow_ctrl':{'bg':'#2a1a2a','text':'#e879f9','header':'#2a1a2a'},'function':{'bg':'#1e2a3a','text':'#7dd3fc','header':'#1e2a3a'},'class':{'bg':'#2a1e2a','text':'#c4b5fd','header':'#2a1e2a'},'unsafe_block':{'bg':'#3a0a0a','text':'#fca5a5','header':'#3a0a0a'},'error_check':{'bg':'#3a1a0a','text':'#fb923c','header':'#3a1a0a'},'defer':{'bg':'#1a1a3a','text':'#a5b4fc','header':'#1a1a3a'},'select':{'bg':'#2a1a0a','text':'#fb923c','header':'#2a1a0a'},'other':{'bg':'#0a0a0a','text':'#4a4a4a','header':'#0a0a0a'}},
}

# ── Color utilities ───────────────────────────────────────────────

def hex_to_rgb(h: str) -> tuple[int,int,int]:
    h = h.lstrip('#')
    return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

def relative_luminance(h: str) -> float:
    def c(v: float) -> float:
        v /= 255
        return v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4
    r,g,b = hex_to_rgb(h)
    return 0.2126*c(r) + 0.7152*c(g) + 0.0722*c(b)

def contrast_ratio(h1: str, h2: str) -> float:
    l1, l2 = relative_luminance(h1), relative_luminance(h2)
    bright, dark = max(l1,l2), min(l1,l2)
    return (bright + 0.05) / (dark + 0.05)

def wcag_grade(ratio: float) -> str:
    if ratio >= 7:   return 'AAA'
    if ratio >= 4.5: return 'AA'
    if ratio >= 3:   return 'AA Large'
    return '❌ Fail'

def is_valid_hex(h: str) -> bool:
    return bool(re.match(r'^#[0-9A-Fa-f]{6}$', h))

# ── Validation ───────────────────────────────────────────────────

def validate(theme: dict, strict: bool = False) -> list[str]:
    errors: list[str] = []

    # Required fields
    for field in ('id','name','type'):
        if field not in theme:
            errors.append(f'缺少必填欄位: {field!r}')

    if theme.get('id') == 'dark':
        errors.append("id 不可為 'dark'（預設主題保留）")
    if not re.match(r'^[a-z0-9-]+$', theme.get('id','')):
        errors.append("id 只能包含小寫英文、數字和連字號")

    if theme.get('type') not in ('dark','light'):
        errors.append("type 必須為 'dark' 或 'light'")

    # Colors
    colors = theme.get('colors', {})
    for key in REQUIRED_COLORS:
        if key not in colors:
            if strict:
                errors.append(f'缺少 colors.{key}')
            # else: will use defaults
        elif not is_valid_hex(str(colors.get(key,''))):
            errors.append(f'colors.{key} 不是有效的十六進制色碼（需 #RRGGBB）')

    # Nodes (only validate if provided)
    nodes = theme.get('nodes', {})
    for nt in NODE_TYPES:
        if nt in nodes:
            for f in REQUIRED_NODE_FIELDS:
                val = nodes[nt].get(f,'')
                if val and not is_valid_hex(str(val)):
                    errors.append(f'nodes.{nt}.{f} 不是有效色碼')

    return errors

# ── Load & merge with defaults ───────────────────────────────────

def load_theme(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding='utf-8'))

    # Handle extends
    base = dict(DARK_DEFAULTS)
    if 'extends' in raw and raw['extends'] != 'dark':
        ext_path = THEMES_DIR / f"{raw['extends']}.json"
        if ext_path.exists():
            ext = json.loads(ext_path.read_text(encoding='utf-8'))
            _deep_merge(base, ext)

    # Merge raw into base
    merged = {**raw}
    merged['colors'] = {**base.get('colors',{}), **raw.get('colors',{})}
    merged['nodes']  = {}
    for nt in NODE_TYPES:
        merged['nodes'][nt] = {
            **base.get('nodes',{}).get(nt,{}),
            **raw.get('nodes',{}).get(nt,{}),
        }
    return merged

def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v

# ── CSS generation ───────────────────────────────────────────────

def build_css(theme: dict) -> str:
    tid   = theme['id']
    c     = theme['colors']
    nodes = theme.get('nodes', {})
    font  = theme.get('font', '')
    font_decl = f"\n  --sans:'{font}';" if font else ''

    # Base vars
    css = f"""/* PyFlow Theme: {theme['name']} */
/* Generated by build_theme.py — do not edit manually */
body.theme-{tid} {{
  --bg:{c['bg']};--bg2:{c['bg2']};--bg3:{c['bg3']};--bg4:{c['bg4']};--bg5:{c['bg5']};
  --bd:{c['bd']};--bd2:{c['bd2']};--bd3:{c['bd3']};
  --tx:{c['tx']};--tx2:{c['tx2']};--tx3:{c['tx3']};--tx4:{c['tx4']};
  --acc:{c['acc']};--acc2:{c['acc2']};--acc3:{c['acc3']};
  --sel:{c['sel']};--ya:{c['ya']};{font_decl}
}}
"""

    # Toolbar
    css += f"""body.theme-{tid} .tbar{{background:{c['bg2']};border-bottom:1px solid {c['bd']};}}
body.theme-{tid} .tlogo{{color:{c['acc']};}}
body.theme-{tid} .tbtn{{color:{c['tx2']};}}
body.theme-{tid} .tbtn:hover{{background:{c['bg3']};color:{c['tx3']};}}
body.theme-{tid} .tbtn.prim{{background:{c['sel']};color:{c['acc3']};border:1px solid {c['bd3']};}}
body.theme-{tid} .tbtn.prim:hover{{background:{c['bg4']};}}
body.theme-{tid} .tsep{{background:{c['bd']};}}
body.theme-{tid} #cdot.ok{{background:{c['acc']} !important;}}
"""

    # Sidebar
    css += f"""body.theme-{tid} .sb{{background:{c['bg2']};border-right:1px solid {c['bd']};}}
body.theme-{tid} .sb-hdr{{background:{c['bg2']};border-bottom:1px solid {c['bd']};color:{c['tx2']};}}
body.theme-{tid} .ib{{color:{c['tx2']};}}
body.theme-{tid} .ib:hover{{color:{c['tx3']};background:{c['bg3']};}}
body.theme-{tid} .ti{{color:{c['tx']};}}
body.theme-{tid} .ti:hover{{background:rgba(128,128,128,.05);}}
body.theme-{tid} .ti.act{{background:{c['sel']};border-left-color:{c['acc']};color:{c['acc3']};}}
"""

    # Editor tabs
    css += f"""body.theme-{tid} .ep{{border-right:1px solid {c['bd']};}}
body.theme-{tid} .tbr{{background:{c['bg2']};border-bottom:1px solid {c['bd']};}}
body.theme-{tid} .tab{{background:{c['bg2']};border-right:1px solid {c['bd']};color:{c['tx2']};}}
body.theme-{tid} .tab.act{{background:{c['bg']};color:{c['tx3']};border-top-color:{c['acc']};}}
body.theme-{tid} #mc{{background:{c['bg']};}}
"""

    # Diagram
    css += f"""body.theme-{tid} .dgtb{{background:{c['bg2']};border-bottom:1px solid {c['bd']};}}
body.theme-{tid} .chip{{background:{c['bg']};border:1px solid {c['bd2']};color:{c['tx2']};}}
body.theme-{tid} .chip:hover{{background:{c['bg3']};color:{c['tx3']};}}
body.theme-{tid} .zb{{background:{c['bg']};border:1px solid {c['bd2']};color:{c['tx2']};}}
body.theme-{tid} .zb:hover{{background:{c['bg3']};color:{c['tx3']};}}
body.theme-{tid} #zpct{{color:{c['tx2']};}}
body.theme-{tid} .dbar{{background:{c['bg2']};border-top:1px solid {c['bd']};color:{c['tx2']};}}
body.theme-{tid} .dbar code{{background:{c['bg3']};border:1px solid {c['bd2']};color:{c['acc3']};}}
body.theme-{tid} .hbar{{background:{c['bg']};border:1px solid {c['bd']};color:{c['tx2']};}}
"""

    # SVG nodes
    is_light = theme.get('type') == 'light'
    nb_fill  = '#ffffff' if is_light else c['bg3']
    css += f"""body.theme-{tid} .nb{{fill:{nb_fill};stroke:{c['bd2']};}}
body.theme-{tid} .nd.sel .nb{{stroke:{c['acc']};stroke-width:1.8;filter:drop-shadow(0 0 8px {c['acc']}44);}}
body.theme-{tid} .nt{{fill:{c['tx3']};}}
body.theme-{tid} .nl{{fill:{c['tx4']};}}
body.theme-{tid} .nd2{{fill:{c['tx2']};}}
body.theme-{tid} .nst{{fill:{c['ya']};}}
body.theme-{tid} .ecl{{opacity:.15;}}
body.theme-{tid} .ecl.hl{{stroke:{c['acc']};opacity:.85;stroke-width:2;}}
body.theme-{tid} .rgt{{fill:{c['tx3']};}}
body.theme-{tid} .rgs{{fill:{c['tx2']};}}
body.theme-{tid} .ncol{{fill:{c['acc']};}}
"""

    # Bottom + search
    css += f"""body.theme-{tid} .bot{{background:{c['bg2']};border-top:1px solid {c['bd']};}}
body.theme-{tid} .btb{{background:{c['bg2']};border-bottom:1px solid {c['bd']};}}
body.theme-{tid} .btt{{color:{c['tx2']};border-right-color:{c['bd']};}}
body.theme-{tid} .btt:hover{{color:{c['tx3']};}}
body.theme-{tid} .btt.act{{color:{c['acc3']};border-bottom-color:{c['acc']};}}
body.theme-{tid} .bi{{color:{c['tx2']};}}
body.theme-{tid} .bi:hover{{color:{c['tx3']};background:{c['bg3']};}}
body.theme-{tid} .or{{background:{c['sel']};color:{c['acc3']};border:1px solid {c['bd3']};}}
body.theme-{tid} .srch-inp{{background:{c['bg3']};color:{c['tx3']};border:1px solid {c['bd2']};}}
body.theme-{tid} .srch-inp:focus{{border-color:{c['acc']};}}
body.theme-{tid} .srch-opt.on{{background:{c['sel']};color:{c['acc3']};border-color:{c['bd3']};}}
body.theme-{tid} .srch-btn{{background:{c['acc']};color:#ffffff;border:none;}}
body.theme-{tid} .sr-file{{background:{c['bg3']};color:{c['acc3']};border-top-color:{c['bd']};}}
body.theme-{tid} .sr-txt mark{{color:{c['ya']};}}
body.theme-{tid} .sr-line:hover{{background:{c['bg3']};}}
"""

    # Palette + settings + toast
    css += f"""body.theme-{tid} .pal-wrap{{background:rgba(0,0,0,.6);}}
body.theme-{tid} .pal{{background:{c['bg3']};border:1px solid {c['bd2']};}}
body.theme-{tid} .pal-in{{background:{c['bg3']};color:{c['tx3']};border-bottom:1px solid {c['bd']};caret-color:{c['acc']};}}
body.theme-{tid} .palr:hover,.theme-{tid} .palr.act{{background:{c['sel']};}}
body.theme-{tid} .palr-n{{color:{c['tx']};}}
body.theme-{tid} .palr-n mark{{color:{c['ya']};}}
body.theme-{tid} .ctx{{background:{c['bg3']};border:1px solid {c['bd2']};}}
body.theme-{tid} .cxi{{color:{c['tx']};}}
body.theme-{tid} .cxi:hover{{background:{c['sel']};color:{c['acc3']};}}
body.theme-{tid} .sett-wrap{{background:{c['bg2']};border-left:1px solid {c['bd']};}}
body.theme-{tid} .sett-hdr{{color:{c['tx3']};border-bottom-color:{c['bd']};}}
body.theme-{tid} .sett-sec{{color:{c['tx2']};}}
body.theme-{tid} .sett-label{{color:{c['tx']};}}
body.theme-{tid} .sett-val{{background:{c['bg3']};border-color:{c['bd2']};color:{c['acc3']};}}
body.theme-{tid} .sett-toggle.on{{background:{c['acc']};}}
body.theme-{tid} .toast{{background:{c['bg3']};border:1px solid {c['bd2']};color:{c['tx']};}}
body.theme-{tid} .sbar{{background:{c['bg2']};border-top:1px solid {c['bd']};}}
body.theme-{tid} .si{{color:{c['tx2']};}}
body.theme-{tid} .si:hover{{background:{c['bg3']};color:{c['tx']};}}
body.theme-{tid} .rsz:hover,.theme-{tid} .rsz.drag{{background:{c['acc']};}}
"""

    # Dot grid
    dot_color = '#E8E3DA' if is_light else '#0d0d0d'
    css += f"""/* dot-grid: {dot_color} */\n"""

    return css

# ── TI JS object generation ──────────────────────────────────────

def build_ti_js(theme: dict) -> str:
    tid   = theme['id']
    nodes = theme.get('nodes', {})
    lines = [f"const TI_{tid.upper().replace('-','_')} = {{"]
    for nt in NODE_TYPES:
        nd = nodes.get(nt, {})
        bg = nd.get('bg','#0a0a0a')
        tc = nd.get('text','#888888')
        hd = nd.get('header', bg)
        safe_name = {'import':'匯入','assign':'賦值','call':'呼叫','goroutine':'Goroutine','channel':'通道','match':'Match','condition':'條件','loop':'迴圈','context':'上下文','exception':'例外','flow_ctrl':'控制流','function':'函式','class':'類別','unsafe_block':'Unsafe','error_check':'錯誤檢查','defer':'Defer','select':'Select','other':'其他'}.get(nt, nt)
        lines.append(f"  {nt}:{{c:'{bg}',tc:'{tc}',hdr:'{hd}',n:'{safe_name}'}},")
    lines.append('};')
    return '\n'.join(lines)

# ── Full Monaco theme JS ──────────────────────────────────────────

def build_monaco_js(theme: dict) -> str:
    tid = theme['id']
    ed  = theme.get('editor', {})
    if not ed:
        # Auto-generate minimal Monaco theme from colors
        c = theme['colors']
        is_light = theme.get('type') == 'light'
        ed = {
            'base': 'vs' if is_light else 'vs-dark',
            'inherit': True,
            'rules': [],
            'colors': {
                'editor.background':  c['bg'],
                'editor.foreground':  c['tx'],
                'editorCursor.foreground': c['acc'],
                'editor.selectionBackground': c['sel'],
                'editor.lineHighlightBackground': c['bg2'],
                'editorWidget.background': c['bg2'],
                'editorWidget.border': c['bd'],
                'focusBorder': c['acc'],
            }
        }

    safe_id = tid.replace('-','_')
    rules_json = json.dumps(ed.get('rules', []), indent=4)
    colors_json = json.dumps(ed.get('colors', {}), indent=4)

    return f"""const _monacoTheme_{safe_id} = {{
  base: {json.dumps(ed.get('base','vs-dark'))},
  inherit: {json.dumps(ed.get('inherit', True))},
  rules: {rules_json},
  colors: {colors_json},
}};"""

# ── Terminal JS ───────────────────────────────────────────────────

def build_terminal_js(theme: dict) -> str:
    tid  = theme['id']
    safe = tid.replace('-','_')
    term = theme.get('terminal', {})
    if not term:
        c = theme['colors']
        term = {
            'background': c['bg'],
            'foreground': c['tx'],
            'cursor':     c['acc'],
            'cursorAccent': c['bg'],
            'selectionBackground': c['sel'],
        }
    return f"const _termTheme_{safe} = {json.dumps(term, indent=2)};"

# ── Contrast report ───────────────────────────────────────────────

def build_report(theme: dict) -> str:
    c = theme['colors']
    pairs = [
        ('主文字 tx / bg',   c['tx'],  c['bg'],   4.5),
        ('次文字 tx2 / bg',  c['tx2'], c['bg'],   3.0),
        ('強調 acc / bg',    c['acc'], c['bg'],   3.0),
        ('acc3 / bg',        c['acc3'],c['bg'],   3.0),
        ('文字 tx / bg3',    c['tx'],  c['bg3'],  4.5),
        ('強調 acc / sel',   c['acc'], c['sel'],  3.0),
    ]
    lines = [f"\n=== 對比度報告：{theme['name']} ===\n"]
    all_ok = True
    for label, fg, bg, min_ratio in pairs:
        r = contrast_ratio(fg, bg)
        grade = wcag_grade(r)
        ok = r >= min_ratio
        if not ok: all_ok = False
        status = '✅' if ok else '⚠️ '
        lines.append(f"  {status} {label:25}  {r:5.2f}:1  {grade}")
    lines.append(f"\n  {'✅ 所有對比度通過' if all_ok else '⚠️  部分對比度未通過 WCAG AA'}")
    return '\n'.join(lines)

# ── Auto-apply to index.html ──────────────────────────────────────

def apply_to_html(theme: dict, css: str, ti_js: str, monaco_js: str, term_js: str):
    if not INDEX_HTML.exists():
        print(f'❌ 找不到 {INDEX_HTML}')
        return

    src = INDEX_HTML.read_text(encoding='utf-8')
    tid  = theme['id']
    safe = tid.replace('-','_')
    marker_css  = f'/* THEME:{tid}:CSS */'
    marker_js   = f'/* THEME:{tid}:JS */'

    # CSS block
    css_block = f"{marker_css}\n{css}\n{marker_css}"
    if marker_css in src:
        # Replace existing
        src = re.sub(re.escape(marker_css)+r'.*?'+re.escape(marker_css), css_block, src, flags=re.S)
    else:
        # Insert before animation
        src = src.replace('@media(prefers-reduced-motion', css_block+'\n@media(prefers-reduced-motion', 1)

    # JS block (TI + Monaco + terminal + setTheme extension)
    dot_color = '#E8E3DA' if theme.get('type')=='light' else '#0d0d0d'
    preview_bg = theme['colors']['bg']
    preview_text = theme['colors']['tx']
    preview = theme.get('preview','🎨')
    name = theme['name']

    js_block = f"""{marker_js}
{ti_js}
{monaco_js}
{term_js}
/* Auto-register theme: {tid} */
(function(){{
  const _orig = setTheme;
  // Extend setTheme to handle {tid}
  const _realSetTheme = window._realSetTheme || _orig;
  if(!window._customThemes) window._customThemes = {{}};
  window._customThemes['{tid}'] = {{
    ti: TI_{safe.upper()},
    monaco: _monacoTheme_{safe},
    terminal: _termTheme_{safe},
    dotColor: '{dot_color}',
    isLight: {'true' if theme.get('type')=='light' else 'false'},
  }};
}})();
{marker_js}"""

    if marker_js in src:
        src = re.sub(re.escape(marker_js)+r'.*?'+re.escape(marker_js), js_block, src, flags=re.S)
    else:
        src = src.replace('/* ── File tree ─', js_block+'\n/* ── File tree ─', 1)

    # Patch setTheme to handle custom themes
    _patch_set_theme(src, tid)

    # Add to theme preview picker
    tp_id = f'tp-{tid}'
    if tp_id not in src:
        old_picker = "        </div>\n      </div>"
        new_entry = f"""          <div id="{tp_id}" onclick="setTheme('{tid}')" style="background:{preview_bg};cursor:pointer;display:flex;align-items:center;justify-content:center;gap:5px;transition:filter .12s;border-top:1px solid rgba(128,128,128,.1)">
            <span style="font-size:14px">{preview}</span>
            <span style="color:{preview_text};font-size:11px;font-weight:600">{name}</span>
          </div>"""
        src = src.replace(old_picker, new_entry + '\n        </div>\n      </div>', 1)

    INDEX_HTML.write_text(src, encoding='utf-8')
    print(f'✅ 已套用主題 {tid!r} 到 {INDEX_HTML}')

def _patch_set_theme(src: str, tid: str):
    """Ensure setTheme handles custom theme ids."""
    # Check if our extension exists already
    marker = f"// customTheme:{tid}"
    if marker in src:
        return src

    # Find the TI = { block in setTheme and add our case
    old_ti_assign = "  TI = t==='claude' ? {...TI_LIGHT}\n     : t==='steam'  ? {...TI_STEAM}\n     : t==='switch' ? {...TI_SWITCH}\n     : {...TI_DARK};"
    safe = tid.replace('-','_')
    new_ti_assign = f"""  // customTheme:{tid}
  if(window._customThemes&&window._customThemes[t]){{
    TI={{...window._customThemes[t].ti}};
  }} else {{
  TI = t==='claude' ? {{...TI_LIGHT}}
     : t==='steam'  ? {{...TI_STEAM}}
     : t==='switch' ? {{...TI_SWITCH}}
     : {{...TI_DARK}};
  }}"""
    return src.replace(old_ti_assign, new_ti_assign, 1)

# ── CLI ───────────────────────────────────────────────────────────

def list_themes():
    print('\n可用主題：')
    for f in sorted(THEMES_DIR.glob('*.json')):
        if f.name == 'example_custom.json': continue
        try:
            t = json.loads(f.read_text())
            ro = ' [唯讀]' if t.get('readonly') else ''
            print(f"  {t.get('preview','  ')}  {t.get('id','?'):20}  {t.get('name','?')}{ro}")
        except Exception as e:
            print(f"  ❌  {f.name}: {e}")
    print()

def main():
    p = argparse.ArgumentParser(description='PyFlow Theme Builder')
    p.add_argument('theme_file',  nargs='?',  help='主題 JSON 檔案路徑')
    p.add_argument('--validate',  action='store_true', help='只驗證，不輸出')
    p.add_argument('--output',    choices=['css','js','all'], default='all', help='輸出格式')
    p.add_argument('--report',    action='store_true', help='顯示對比度報告')
    p.add_argument('--apply',     action='store_true', help='自動套用到 index.html')
    p.add_argument('--list',      action='store_true', help='列出所有主題')
    p.add_argument('--list-ids',  action='store_true', help='只列出 id')
    args = p.parse_args()

    if args.list:
        list_themes(); return
    if args.list_ids:
        for f in sorted(THEMES_DIR.glob('*.json')):
            try:
                t = json.loads(f.read_text())
                print(t.get('id',''))
            except: pass
        return

    if not args.theme_file:
        p.print_help(); sys.exit(1)

    path = Path(args.theme_file)
    if not path.exists():
        print(f'❌ 找不到檔案：{path}'); sys.exit(1)

    # Load & validate
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw.get('readonly') and args.apply:
        print(f'⚠️  {raw.get("name","?")} 是唯讀主題，無法套用'); sys.exit(1)

    errors = validate(raw, strict=args.validate)
    if errors:
        print(f'❌ 驗證失敗：{path.name}')
        for e in errors: print(f'   • {e}')
        if args.validate: sys.exit(1)
        print('   （繼續使用預設值補足…）\n')
    else:
        print(f'✅ 驗證通過：{raw.get("name","?")} ({raw.get("id","?")})')

    if args.validate:
        print('驗證完成。'); return

    # Load with defaults merged
    theme = load_theme(path)

    # Generate outputs
    css      = build_css(theme)
    ti_js    = build_ti_js(theme)
    monaco_js = build_monaco_js(theme)
    term_js  = build_terminal_js(theme)

    if args.report:
        print(build_report(theme))

    if args.apply:
        apply_to_html(theme, css, ti_js, monaco_js, term_js)
        return

    if args.output in ('css', 'all'):
        print('\n/* ══ CSS ══ */')
        print(css)

    if args.output in ('js', 'all'):
        print('\n/* ══ TI Object ══ */')
        print(ti_js)
        print('\n/* ══ Monaco Theme ══ */')
        print(monaco_js)
        print('\n/* ══ Terminal Theme ══ */')
        print(term_js)

if __name__ == '__main__':
    main()
