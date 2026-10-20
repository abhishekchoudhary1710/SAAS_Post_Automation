"""A readable feed advertisement built from the reviewed fictional scenario."""
from pathlib import Path
from PIL import Image, ImageDraw
from .sales import paragraph, INK, MUTED, GREEN, BLUE
from .fonts import font
from ..config import ROOT, brand


def build_poster(s, script, path):
    colors = {'blue': '#0b192e', 'jade': '#0c2425', 'violet': '#21162e'}
    img = Image.new('RGB', (1080, 1350), colors.get(s.get('_visual', {}).get('theme'), '#0b192e'))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 1080, 12), fill=GREEN)
    logo = Image.open(ROOT / brand()['images']['logo']).convert('RGBA').resize((62, 62))
    img.paste(logo, (86, 65), logo)
    d.text((165, 72), 'Interview Sarthi', font=font(39, 'semibold'), fill=INK)
    d.text((86, 160), 'LIVE INTERVIEW HELP  /  WINDOWS', font=font(27, 'medium'), fill=BLUE)
    paragraph(d, script['hook'], 225, size=74, weight='bold', bottom=480, min_size=52)
    d.rounded_rectangle((65, 510, 1015, 946), radius=24, fill='#142b3b')
    d.text((86, 535), 'INTERVIEWER ASKS', font=font(24, 'semibold'), fill=BLUE)
    paragraph(d, s['question'], 580, size=39, min_size=31, bottom=700)
    d.text((86, 705), 'SUGGESTED ANSWER FROM A FICTIONAL RESUME', font=font(23, 'semibold'), fill=GREEN)
    paragraph(d, s['answer'], 745, size=34, min_size=28, bottom=940)
    paragraph(d, 'It listens during the call. Answers use your resume.', 952, size=32, min_size=30, bottom=1050)
    d.text((86, 1050), 'Hidden from supported screen sharing.*', font=font(30, 'medium'), fill=GREEN)
    d.text((86, 1110), 'Try 30 minutes free.', font=font(57, 'bold'), fill=INK)
    d.text((86, 1190), 'interviewsarthi.com', font=font(42, 'semibold'), fill=BLUE)
    d.text((86, 1260), '*Capture support varies. Windows 10 (2004+)/11.', font=font(23), fill=MUTED)
    d.text((86, 1295), 'Own Gemini key required. Illustrative example.', font=font(23), fill=MUTED)
    if path is None:
        return img
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, 'JPEG', quality=95)
    with Image.open(path) as checked:
        checked.verify()
    return {'images': [str(path)], 'mode': 'sales-image'}
