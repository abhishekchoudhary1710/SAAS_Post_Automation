"""Native motion design, reusable illustrative footage and an original procedural music bed."""
from __future__ import annotations

import functools
import math
import subprocess
import wave
from array import array
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ..config import ROOT, brand
from .fonts import font
from .sales import W, H, FPS, paragraph, lines_for, screenshot
from .reel import ffmpeg_exe

WHITE = '#f5f8ff'
BLUE = '#9cbcff'
GREEN = '#89f0cb'


def ease(value):
    return 1 - (1 - min(1, max(0, value))) ** 3


@functools.lru_cache(maxsize=1)
def footage():
    path = ROOT / 'assets/motion/interview-smooth.mp4'
    if not path.exists():
        path = ROOT / 'assets/motion/interview.mp4'
    if not path.exists():
        return []
    p = subprocess.run([ffmpeg_exe(), '-v', 'error', '-i', str(path), '-t', '6',
                        '-vf', f'fps={FPS},scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280',
                        '-f', 'image2pipe', '-vcodec', 'mjpeg', '-q:v', '4', '-'],
                       capture_output=True, timeout=90, check=True)
    # Keep compressed JPEG frames, not hundreds of megabytes of raw pixels.
    return [b'\xff\xd8' + x for x in p.stdout.split(b'\xff\xd8')[1:]]


@functools.lru_cache(maxsize=1)
def background():
    small = Image.new('RGB', (270, 480), '#080f23')
    d = ImageDraw.Draw(small)
    d.ellipse((-90, 20, 210, 320), fill='#183e82')
    d.ellipse((140, 200, 350, 500), fill='#312557')
    return small.filter(ImageFilter.GaussianBlur(58)).resize((W, H))


def panel(size, fill='#12243e', outline='#36587c'):
    layer = Image.new('RGBA', size)
    ImageDraw.Draw(layer).rounded_rectangle((1, 1, size[0]-2, size[1]-2), 28, fill=fill, outline=outline, width=2)
    return layer


def place(canvas, layer, x, y, t, delay=0, travel=65, zoom=False):
    progress = ease((t-delay)/.65)
    if progress <= 0:
        return
    if zoom:
        scale = .91 + .09*progress
        old = layer.size
        layer = layer.resize((round(old[0]*scale), round(old[1]*scale)), Image.Resampling.BICUBIC)
        x += (old[0]-layer.width)/2
        y += (old[1]-layer.height)/2
    if progress < 1:
        layer = layer.copy()
        layer.putalpha(layer.getchannel('A').point(lambda a: round(a*progress)))
    canvas.paste(layer, (round(x), round(y + travel*(1-progress))), layer)


def text_layer(text, size, width=832, colour=WHITE, weight='bold', height=360):
    result = Image.new('RGBA', (width, height))
    paragraph(ImageDraw.Draw(result), text, 0, size=size, colour=colour, weight=weight,
              x=0, width=width, bottom=height, min_size=size-12)
    return result


class MotionScene:
    def __init__(self, scenario, script, kind):
        self.s, self.script, self.kind = scenario, script, kind
        self.minimum_font = 34
        self.previous = None
        self.shot = screenshot()
        self.logo = Image.open(ROOT / brand()['images']['logo']).convert('RGBA').resize((58, 58))
        self.headline = text_layer(script['hook'] if kind == 'hook' else {
            'answer': 'Your resume.\nYour answer.', 'evidence': 'Your experience\nis the difference.',
            'product': 'Your call stays open.', 'cta': 'Your next interview.\nMeet your Sarthi.'}[kind],
            72 if kind != 'hook' else 76, height=350)

    def shell(self, t):
        img = background().copy()
        if self.kind == 'hook' and footage():
            frames = footage()
            # Play once at the encoded cadence. Loop if a longer opening outlasts the clip.
            img = Image.open(BytesIO(frames[int(t*FPS) % len(frames)])).convert('RGB').resize((W,H))
            shade = Image.new('RGBA', (W,H))
            d = ImageDraw.Draw(shade)
            for y in range(H):
                alpha = round(65 + 160*max(0, (y-650)/1270))
                if y < 650:
                    alpha = round(110 - y*.07)
                d.line((0,y,W,y), fill=(4,10,24,alpha))
            img = Image.alpha_composite(img.convert('RGBA'), shade).convert('RGB')
        d = ImageDraw.Draw(img)
        if self.kind != 'hook':
            for i in range(9):
                x = 70 + (i*139 + t*(12+i%3*4)) % 970
                y = 360 + (i*227 - t*20) % 1140
                d.ellipse((x,y,x+3,y+3), fill='#587db0')
            r = 240 + 15*math.sin(t*.9)
            d.ellipse((730-r,990-r,730+r,990+r), outline='#244269', width=2)
        img.paste(self.logo,(86,160),self.logo)
        d.text((161,165),'Interview Sarthi',font=font(34,'semibold'),fill=WHITE)
        d.text((86,1605),'Windows 10/11  |  interviewsarthi.com',font=font(26),fill='#cad8ed')
        disclosure = 'Illustrative scene / fictional resume / edited timing'
        d.text((86,1650),disclosure,font=font(22),fill='#adbbce')
        return img

    def question(self, t, width=832):
        box = panel((width,250),'#142945','#547aaa')
        d = ImageDraw.Draw(box)
        d.ellipse((28,28,43,43),fill=GREEN)
        d.text((58,18),'INTERVIEWER',font=font(23,'semibold'),fill=BLUE)
        words=self.s['question'].split()
        shown=' '.join(words[:max(1,round(t*14))])
        paragraph(d,shown,74,size=44,x=28,width=width-56,bottom=235,min_size=36,colour=WHITE)
        for i in range(15):
            amp=5+18*abs(math.sin(t*6+i*.85))
            x=width-155+i*7
            d.line((x,36-amp/2,x,36+amp/2),fill=GREEN,width=3)
        return box

    def suggested(self, t, full=True):
        box = panel((832,720 if full else 285),'#f0f5ff','#d8e6ff')
        d=ImageDraw.Draw(box)
        d.rounded_rectangle((25,24,292,69),12,fill='#d9e9ff')
        d.text((41,30),'SUGGESTED ANSWER',font=font(23,'semibold'),fill='#2456a0')
        answer=self.s['answer'] if full else self.s['answer'].split('. ')[0].rstrip('.')+'.'
        # Answer becomes fully readable quickly, then stays still while supporting graphics move.
        words=answer.split()
        shown=' '.join(words[:max(1,int(t*23))])
        paragraph(d,shown,100,size=47 if full else 36,x=30,width=772,
                  bottom=650 if full else 275,min_size=38 if full else 32,colour='#132844')
        if full:
            d.rounded_rectangle((25,641,807,698),12,fill='#d7eee6')
            d.text((43,651),self.s['benefit'],font=font(29,'medium'),fill='#165846')
        return box

    def privacy_frame(self,t):
        img = self.shell(t)
        title = text_layer('On your screen. Out of the share.', 72, height=350)
        place(img,title,86,285,t,travel=45)
        for i,label in enumerate(('YOUR SCREEN', 'INTERVIEWER / SHARED VIEW')):
            box = panel((832,340),'#102340','#44668e')
            d = ImageDraw.Draw(box)
            d.text((26,20),label,font=font(28,'semibold'),fill=GREEN if i==0 else BLUE)
            # Both views have identical shared content; only the local view has Sarthi.
            d.rounded_rectangle((25,79,807,316),16,fill='#e7eef9')
            d.text((46,97),'Project notes',font=font(27,'semibold'),fill='#183557')
            for row in range(4):
                d.rounded_rectangle((46,159+row*31,685-row*53,169+row*31),5,fill='#a7bad4')
            if i==0:
                overlay = panel((355,187),'#214b65','#89f0cb')
                od=ImageDraw.Draw(overlay)
                od.text((20,18),'Interview Sarthi',font=font(27,'semibold'),fill=WHITE)
                od.text((20,70),'Suggested answer',font=font(24),fill=GREEN)
                for row in range(2):
                    od.rounded_rectangle((20,125+row*24,310-row*55,133+row*24),4,fill='#8bb4ca')
                place(box,overlay,426,119,t,.18,travel=40)
            place(img,box,86,685+i*413,t,i*.15,travel=60)
        note=text_layer('Screen-share exclusion on supported Windows setups.',32,
                        colour=GREEN,weight='medium',height=115)
        place(img,note,86,1460,t,.3,travel=25)
        ImageDraw.Draw(img).text((86,1560),'Windows 10 (2004+) / 11. Capture support varies.',font=font(25),fill='#cad8ed')
        return img

    def raw_frame(self,t,duration):
        img=self.shell(t)
        d=ImageDraw.Draw(img)
        if self.kind=='hook':
            place(img,self.headline,86,285,t,travel=45)
            place(img,self.question(t),86,922,t,.15,travel=90)
            if t>=1.1:
                place(img,self.suggested(t-1.05,False),86,1225,t,1.1,travel=100)
        elif self.kind=='answer':
            place(img,self.headline,86,285,t)
            place(img,self.question(9),86,605,t,.05)
            place(img,self.suggested(t,True),86,885,t,travel=70)
        elif self.kind=='evidence':
            place(img,self.headline,86,290,t)
            doc=panel((720,575),'#f0f5ff','#d8e6ff')
            dd=ImageDraw.Draw(doc)
            dd.text((38,34),'RESUME / '+self.s['name'].upper(),font=font(26,'semibold'),fill='#526581')
            paragraph(dd,self.s['evidence'][0],115,size=46,x=38,width=644,bottom=300,min_size=36,colour='#142640')
            for i in range(3): dd.rounded_rectangle((38,300+i*48,620-i*55,312+i*48),6,fill='#d3dce9')
            place(img,doc,130,665+8*math.sin(t),t,.12,zoom=True)
            evidence=panel((832,205),'#173c3d','#61cba4')
            paragraph(ImageDraw.Draw(evidence),self.s['evidence'][1],32,size=41,x=30,width=772,bottom=188,min_size=34,colour=GREEN)
            # A resume detail visibly travels down into the highlighted answer evidence.
            fly=ease((t-.8)/1.1)
            place(img,evidence,86,970+340*fly,t,.7,travel=0)
        elif self.kind=='product':
            place(img,self.headline,86,290,t)
            place(img,text_layer('Live help, alongside your meeting.',40,colour=BLUE,weight='medium',height=140),86,560,t,.15)
            laptop=panel((924,650),'#0a1122','#5576a2')
            shot=self.shot.resize((876,515))
            # A slow camera move focuses the real screenshot without inventing interface content.
            scale=1 + .07*ease(t/max(1,duration-1))
            zoom=shot.resize((round(876*scale),round(515*scale)),Image.Resampling.BICUBIC)
            x=(zoom.width-876)//2; y=zoom.height-515
            laptop.paste(zoom.crop((x,y,x+876,y+515)),(24,60))
            ld=ImageDraw.Draw(laptop)
            ld.text((27,17),'ACTUAL APP INTERFACE',font=font(22,'semibold'),fill=BLUE)
            ld.rounded_rectangle((0,600,923,646),15,fill='#7086a6')
            ld.rounded_rectangle((350,600,574,616),8,fill='#283e60')
            place(img,laptop,60,800+8*math.sin(t*1.1),t,.2,travel=110,zoom=True)
            for i,label in enumerate(['Teams','Zoom','Google Meet']):
                badge=panel((258,75),'#213963','#5276a8')
                ImageDraw.Draw(badge).text((20,17),label,font=font(30,'medium'),fill=WHITE)
                place(img,badge,86+i*286,1480,t,.45+i*.14,travel=40)
            if t >= 2.4:
                privacy = self.privacy_frame(t-2.4)
                img = Image.blend(img, privacy, ease((t-2.4)/.4))
        else:
            place(img,self.headline,86,290,t)
            ring=Image.new('RGBA',(600,600))
            rd=ImageDraw.Draw(ring)
            for i in range(3):
                inset=15+i*25
                rd.arc((inset,inset,600-inset,600-inset),t*35+i*110,t*35+i*110+185,fill=['#447bd8','#679eec','#97e7d0'][i],width=4)
            img.paste(ring,(240,625),ring)
            offer=text_layer('30',205,width=550,height=285)
            place(img,offer,336,710,t,.12,zoom=True)
            place(img,text_layer('minutes free',60,width=640,height=105),272,975,t,.3)
            place(img,text_layer('No payment card.',35,width=650,colour=GREEN,weight='medium',height=90),307,1113,t,.5)
            place(img,text_layer('Then Rs 99 for 2 days.',45,width=832,height=105),86,1280,t,.6)
            cta=panel((832,110),'#bceedd','#bceedd')
            cd=ImageDraw.Draw(cta)
            cd.text((33,23),'interviewsarthi.com',font=font(47,'semibold'),fill='#0f3b35')
            arrow=round(12*math.sin(t*3))
            cd.line((747+arrow,55,785+arrow,55),fill='#0f3b35',width=5)
            cd.line((770+arrow,39,787+arrow,55,770+arrow,71),fill='#0f3b35',width=5)
            place(img,cta,86,1410,t,.75,travel=50)
            d=ImageDraw.Draw(img)
            d.text((86,1545),'Setup uses your own Google Gemini key.',font=font(26),fill='#cad8ed')
        return img

    def frame(self,t,duration):
        current=self.raw_frame(t,duration)
        if self.previous and t<.34:
            # Transition within the scene budget: audio timing remains unchanged.
            previous,previous_duration=self.previous
            old=previous.raw_frame(previous_duration-.01,previous_duration)
            progress=ease(t/.34)
            shifted=Image.new('RGB',(W,H),'#080f23')
            shifted.paste(current,(round(100*(1-progress)),0))
            current=Image.blend(old,shifted,progress)
        return current


def music_bed(path: Path, seconds: float, cuts: list[float]):
    """Original quiet synth pulse and transition sweeps; no downloaded music or licensing dependency."""
    rate=22050
    samples=array('h')
    chords=[(164.81,207.65,246.94),(130.81,164.81,196),(146.83,185,220),(123.47,155.56,185)]
    for n in range(math.ceil(seconds*rate)):
        t=n/rate
        chord=chords[int(t/4)%4]
        beat=t%.5
        pad=sum(math.sin(2*math.pi*f*t) for f in chord)*.016
        pluck=math.sin(2*math.pi*chord[int(t*2)%3]*2*t)*math.exp(-beat*13)*.045
        tick=math.sin(2*math.pi*(1400+200*math.sin(t*17))*t)*math.exp(-beat*100)*.008
        sweep=0
        for cut in cuts:
            delta=t-cut
            if -.18<delta<.3:
                env=math.sin(math.pi*(delta+.18)/.48)**2
                sweep+=math.sin(2*math.pi*(300*delta+800*delta*delta))*env*.025
        fade=min(1,t/.4,(seconds-t)/.7)
        samples.append(int(32767*max(0,fade)*(pad+pluck+tick+sweep)))
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate); out.writeframes(samples.tobytes())
