"""Draw the application icon (a small spreadsheet with changed cells) -> desktop/icons/app.png and app.ico."""
from pathlib import Path
from PIL import Image,ImageDraw

SIZE=1024
BLUE,LINE,HEADER='#2563eb','#bcd0f7','#dbe7fd'
ORANGE,GREEN,RED='#f59e0b','#22c55e','#ef4444'


def draw():
    image=Image.new('RGBA',(SIZE,SIZE),(0,0,0,0));pen=ImageDraw.Draw(image)
    pen.rounded_rectangle((0,0,SIZE-1,SIZE-1),radius=230,fill=BLUE)
    left,top,right,bottom=170,200,SIZE-170,SIZE-200;cell_w=(right-left)/3;cell_h=(bottom-top)/4
    pen.rounded_rectangle((left,top,right,bottom),radius=48,fill='white')
    pen.rounded_rectangle((left,top,right,top+cell_h),radius=48,fill=HEADER);pen.rectangle((left,top+cell_h/2,right,top+cell_h),fill=HEADER)
    changed={(1,1):ORANGE,(2,2):GREEN,(0,3):RED}
    for (column,row),color in changed.items():
        x0=left+column*cell_w+14;y0=top+row*cell_h+14;pen.rounded_rectangle((x0,y0,x0+cell_w-28,y0+cell_h-28),radius=22,fill=color)
    for column in range(1,3):pen.line((left+column*cell_w,top,left+column*cell_w,bottom),fill=LINE,width=10)
    for row in range(1,4):pen.line((left,top+row*cell_h,right,top+row*cell_h),fill=LINE,width=10)
    return image


if __name__=='__main__':
    target=Path(__file__).resolve().parents[1]/'desktop'/'icons';image=draw()
    image.resize((256,256),Image.LANCZOS).save(target/'app.png')
    image.save(target/'app.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
