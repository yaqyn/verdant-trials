"""Shared visual tokens and native widget styles."""
from tkinter import ttk, font

COLORS = dict(background='#eef2f5', surface='#ffffff', ink='#183348', muted='#526878',
              accent='#087f82', accent_light='#d8eeee', wall='#263f50',
              explored='#dce9f4', retreat='#e8e2d7', route='#0b7970', player='#b54d28')


def configure(root):
    root.configure(background=COLORS['background'])
    font.nametofont('TkDefaultFont').configure(family='DejaVu Sans', size=10)
    root.option_add('*Font', 'TkDefaultFont')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=COLORS['background'], foreground=COLORS['ink'])
    style.configure('TFrame', background=COLORS['background'])
    style.configure('Panel.TFrame', background=COLORS['surface'])
    style.configure('TLabel', background=COLORS['background'], foreground=COLORS['ink'])
    style.configure('Title.TLabel', font=('DejaVu Sans', 24, 'bold'))
    style.configure('Heading.TLabel', font=('DejaVu Sans', 13, 'bold'))
    style.configure('Muted.TLabel', foreground=COLORS['muted'])
    style.configure('TButton', padding=(10, 6))
    style.map('TButton', background=[('active', COLORS['accent_light'])])
    style.configure('Accent.TButton', background=COLORS['accent'], foreground='white')
    style.map('Accent.TButton', background=[('active', '#09666b'), ('disabled', '#d9e1e6')],
              foreground=[('disabled', '#647783')])
    style.configure('TCombobox', padding=4)
