"""Forest-quest palette and shared native widget styles.

COLORS retains its identity when switching themes so canvas consumers can hold
one reference. Exact palette values live here; DESIGN.md records their roles.
"""
from tkinter import ttk, font
from typography import families

THEMES = {
    'dark': dict(background='#101914', surface='#14231c', panel='#1b2921',
                 ink='#eee7d2', muted='#b8bea9', accent='#d4b977',
                 accent_light='#354636', wall='#a0a184', explored='#304c50',
                 retreat='#59493a', route='#e3c77f', player='#eab77b',
                 border='#68704d', field='#233128', disabled='#8e9787',
                 error='#f0a89b', trail='#677c66', on_accent='#1a241b'),
    'light': dict(background='#e9e8dc', surface='#f6f3e6', panel='#dedfce',
                  ink='#25392b', muted='#52604d', accent='#72531f',
                  accent_light='#d3d7be', wall='#53664d', explored='#cadbdd',
                  retreat='#ddcfb7', route='#816020', player='#8a461f',
                  border='#8a9377', field='#f9f7ee', disabled='#707866',
                  error='#9a352b', trail='#8d9f82', on_accent='#fff9e8'),
}
COLORS = dict(THEMES['dark'])
FONTS = {'heading': 'serif', 'body': 'sans'}


def configure(root, mode='dark'):
    if mode not in THEMES:
        raise ValueError("Theme must be 'dark' or 'light'")
    COLORS.clear()
    COLORS.update(THEMES[mode])
    c = COLORS
    heading, body = families(root)
    FONTS.update(heading=heading, body=body)
    root.configure(background=c['background'])
    for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
        font.nametofont(name, root=root).configure(family=body, size=10)
    root.option_add('*Font', 'TkDefaultFont')
    root.option_add('*TCombobox*Listbox.background', c['field'])
    root.option_add('*TCombobox*Listbox.foreground', c['ink'])
    root.option_add('*TCombobox*Listbox.selectBackground', c['accent'])
    root.option_add('*TCombobox*Listbox.selectForeground', c['on_accent'])
    root.option_add('*TCombobox*Listbox.font', 'TkDefaultFont')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=c['background'], foreground=c['ink'],
                    font=(body, 10), bordercolor=c['border'],
                    lightcolor=c['border'], darkcolor=c['border'],
                    troughcolor=c['surface'], focuscolor=c['accent'])
    style.configure('TFrame', background=c['background'])
    style.configure('Panel.TFrame', background=c['panel'])
    style.configure('TLabel', background=c['background'], foreground=c['ink'])
    style.configure('Panel.TLabel', background=c['panel'], foreground=c['ink'])
    style.configure('Title.TLabel', font=(heading, 26), foreground=c['accent'])
    style.configure('Heading.TLabel', font=(heading, 12, 'bold'), foreground=c['ink'])
    style.configure('Quest.TLabel', font=(heading, 16), foreground=c['accent'])
    style.configure('Muted.TLabel', foreground=c['muted'])
    style.configure('Error.TLabel', foreground=c['error'])
    style.configure('TSeparator', background=c['border'])
    style.configure('TButton', padding=(10, 6), background=c['panel'],
                    foreground=c['ink'], borderwidth=1, relief='flat',
                    focusthickness=2, focuscolor=c['accent'])
    style.map('TButton', background=[('disabled', c['background']), ('pressed', c['field']),
                                   ('active', c['accent_light'])],
              foreground=[('disabled', c['disabled']), ('active', c['ink'])],
              bordercolor=[('focus', c['accent']), ('active', c['accent'])])
    style.configure('Accent.TButton', background=c['accent'], foreground=c['on_accent'])
    style.map('Accent.TButton', background=[('disabled', c['panel']), ('pressed', c['accent_light']),
                                          ('active', c['ink'])],
              foreground=[('disabled', c['disabled']), ('pressed', c['ink']),
                          ('active', c['on_accent'])])
    for widget in ('TEntry', 'TCombobox', 'TSpinbox'):
        style.configure(widget, padding=4, fieldbackground=c['field'], background=c['panel'],
                        foreground=c['ink'], arrowcolor=c['accent'], insertcolor=c['ink'],
                        selectbackground=c['accent'], selectforeground=c['on_accent'])
        style.map(widget, fieldbackground=[('disabled', c['background']), ('readonly', c['field'])],
                  foreground=[('disabled', c['disabled']), ('readonly', c['ink'])],
                  bordercolor=[('focus', c['accent'])],
                  arrowcolor=[('disabled', c['disabled']), ('active', c['ink'])],
                  background=[('active', c['accent_light']), ('readonly', c['panel'])])
    style.configure('TCheckbutton', background=c['background'], foreground=c['ink'])
    style.map('TCheckbutton', background=[('active', c['background'])],
              foreground=[('disabled', c['disabled'])], indicatorcolor=[('selected', c['accent'])])
    return mode
