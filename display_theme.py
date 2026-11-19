"""Colour tokens for the native desktop themes."""

THEMES = {
    'light': ('라이트', 'light', '#ffffff', '#f3f6fa', '#ffffff', '#243247', '#64748b', '#d4dce7', '#e5edf8'),
    'gray': ('소프트 그레이', 'light', '#e9edf1', '#f3f5f7', '#f8fafc', '#263345', '#566579', '#bcc6d2', '#dbe3ec'),
    'warm': ('웜', 'light', '#f5f0e6', '#eee7da', '#fffbf2', '#433d34', '#736958', '#d0c4b0', '#e6dcc9'),
    'dark': ('다크', 'dark', '#151b25', '#202938', '#263244', '#e2e8f0', '#a4b3ca', '#495a70', '#35455c'),
    'navy': ('네이비', 'dark', '#101b30', '#192941', '#223753', '#e0ebfa', '#a6bad7', '#435d7e', '#2e4868'),
    'charcoal': ('차콜', 'dark', '#111315', '#1d2024', '#292d32', '#e6e8ec', '#adb4be', '#4b535e', '#383f48'),
}

def _luminance(color):
    color=color.lstrip('#');red,green,blue=[int(color[i:i+2],16)/255 for i in (0,2,4)]
    channel=lambda c:c/12.92 if c<=.03928 else ((c+.055)/1.055)**2.4
    return .2126*channel(red)+.7152*channel(green)+.0722*channel(blue)


def contrast(first,second):
    high,low=sorted((_luminance(first),_luminance(second)),reverse=True);return (high+.05)/(low+.05)


def _mix(start,end,amount):
    a,b=start.lstrip('#'),end.lstrip('#')
    return '#'+''.join(f'{round(int(a[i:i+2],16)*(1-amount)+int(b[i:i+2],16)*amount):02x}' for i in (0,2,4))


def ensure_contrast(color,backgrounds,target,toward):
    """Move `color` toward `toward` (usually the text colour) until it reaches `target`:1 on every background."""
    for step in range(0,21):
        candidate=_mix(color,toward,step/20)
        if all(contrast(candidate,background)>=target for background in backgrounds):return candidate
    return toward


def palettes():
    result={}
    for name,(label,base,*values) in THEMES.items():
        tokens=dict(zip(('bg','panel','input','text','muted','border','hover'),values))
        tokens.update({'add':'#163e2c','add-text':'#a0edba','edit':'#58391c','edit-text':'#ffd39c','delete':'#54262c','delete-text':'#ffb5ba'} if base=='dark' else {'add':'#dcfce7','add-text':'#176038','edit':'#ffedd5','edit-text':'#8a3a06','delete':'#fee2e2','delete-text':'#9b2424'})
        surfaces=(tokens['bg'],tokens['panel'],tokens['input'])
        # Helper text must read as body text (4.5:1) and control outlines must be visible (3:1) on every surface.
        tokens['muted']=ensure_contrast(tokens['muted'],surfaces,4.5,tokens['text'])
        tokens['control']=ensure_contrast(tokens['border'],surfaces,3.0,tokens['text'])
        tokens['ring']='#60a5fa' if base=='dark' else '#2563eb'
        result[name]={'label':label,'base':base,'tokens':tokens}
    return result
