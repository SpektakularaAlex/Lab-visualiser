import tkinter as tki
from math import floor, ceil, log10

DEBUG = False

if DEBUG: import time

''' usage:
        self.chart = mychart.Chart(self.master, 350, 350)
        self.chart.place(x=0, y=100)
        self.chart.draw([212e-4, 222e-4, 232e-4, 242e-4, 252e-4], [[2, 4, 6, 8, 16], [1, 3, 5, 7, 9]])
'''

class Chart(tki.Canvas):
    def __init__(self, master, awidth, aheight, x_axis_title = ''):
        super().__init__(master, width=awidth, height=aheight)
        self.chartWidth = awidth
        self.chartHeight = aheight
        self.marginL = self.marginT = self.marginB = self.marginR = 40
        self.colors      = ['red', 'blue', 'black', 'gold', 'green']
        self.colors_pale = ['#ff8888', '#8888ff', '#888888', '#ffff00', '#44cc44']
        self.innerHeightPx= self.chartHeight- self.marginT - self.marginB
        self.tmpcanvas = tki.Canvas(master, width=1, height=1)
        self.tmptext = self.tmpcanvas.create_text(0, 0, text='')
        self.create_text(awidth / 2, aheight - 14, text=x_axis_title, anchor='center', tags='const')  # Y label
        
        
    def getTextWidth(self, fmt, v1, v2):
        self.tmpcanvas.itemconfigure(self.tmptext, text=fmt.format(v1))
        bb = self.tmpcanvas.bbox(self.tmptext)
        wi = bb[2]-bb[0]
        self.tmpcanvas.itemconfigure(self.tmptext, text=fmt.format(v2))
        bb = self.tmpcanvas.bbox(self.tmptext)
        return max(wi, bb[2]-bb[0])
        
        
    def clear(self):
        self.delete('axes')
        self.delete('series')
        
        
    def draw(self, x_values, y_values, y2_values=None, y_legend=None, y2_legend=None, y_bands=None, y2_bands=None):
        if DEBUG: t0 = time.time()
        if y2_values is None:
            y2_values = []
        if y_legend is None:
            y_legend = []
        if y2_legend is None:
            y2_legend = []
        if y_bands is None:
            y_bands = []
        if y2_bands is None:
            y2_bands = []

        self.marginT = 18 + 13*max(len(y_legend), len(y2_legend))
        self.innerHeightPx = self.chartHeight - self.marginT - self.marginB
        
        self.delete('axes')
        self.delete('series')

        # Draw Y ticks and labels:        
        if len(y_values) > 0:
            ymin = min(min(y) for y in y_values)
            ymax = max(max(y) for y in y_values)
            for band in y_bands:
                if len(band)>0:
                    ymin = min(ymin, min(band))
                    ymax = max(ymax, max(band))
            if ymax == ymin:
                ymin -= 0.001
                ymax += 0.001
            span = ymax-ymin
            step = span/4 # we want to split the span in min 4 parts, so this is the maximal step size
            l10 = floor(log10(step))
            p10 = 10**l10 # the power of 10 that is just lower than the step
            ss = step/p10 # this should be a number between 1 and 9.9999
            ss = 5 if ss>=5 else 2 if ss>=2 else 1 # shorten the step to be a multiple of 1, 2 or 5
            step = ss*p10 # this is the new step size, perhaps smaller than the original
            ymin = floor(ymin/step)*step
            ymax =  ceil(ymax/step)*step
            span = ymax-ymin
            stepcnt = round(span/step)
            y_coef_mult = -self.innerHeightPx/span
            y_coef_add = self.marginT - y_coef_mult*ymax
            color = 'black' if len(y_values)!=1 or len(y2_values)==0 else self.colors[0]
            digits = max(0, -l10)
            fmts = '{:.'+str(digits)+'f}'
            textwid = self.getTextWidth(fmts, ymin, ymin+step*stepcnt)
            self.marginL = textwid+8
            for i in range(stepcnt + 1):
                y_coord = self.chartHeight-self.marginB - round(i * self.innerHeightPx/stepcnt)
                self.create_line(self.marginL-4, y_coord, self.marginL, y_coord, fill=color, tags='axes')  # Y tick
                self.create_text(self.marginL-8, y_coord, text=fmts.format(ymin+i*step), fill=color, tags='axes', anchor='e')  # Y label


        # Draw Y2 ticks and labels
        if len(y2_values) > 0:
            y2min = min(min(y) for y in y2_values)
            y2max = max(max(y) for y in y2_values)
            for band in y2_bands:
                if len(band)>0:
                    y2min = min(y2min, min(band))
                    y2max = max(y2max, max(band))
            if y2max == y2min:
                y2min -= 0.001
                y2max += 0.001
            span = y2max-y2min
            step = span/4 # we want to split the span in min 4 parts, so this is the maximal step size
            l10 = floor(log10(step))
            p10 = 10**l10 # the power of 10 that is just lower than the step
            ss = step/p10 # this should be a number between 1 and 9.9999
            ss = 5 if ss>=5 else 2 if ss>=2 else 1 # shorten the step to be a multiple of 1, 2 or 5
            step = ss*p10 # this is the new step size, perhaps smaller than the original
            y2min = floor(y2min/step)*step
            y2max =  ceil(y2max/step)*step
            span = y2max-y2min
            stepcnt = round(span/step)
            y2_coef_mult = -self.innerHeightPx/span
            y2_coef_add = self.marginT - y2_coef_mult*y2max
            color = 'black' if len(y2_values)!=1 or len(y_values)==0 else self.colors[len(y_values)]
            digits = max(0, -l10)
            fmts = '{:.'+str(digits)+'f}'
            textwid = self.getTextWidth(fmts, y2min, y2min+step*stepcnt)
            self.marginR = textwid+8
            for i in range(stepcnt + 1):
                y_coord = self.chartHeight-self.marginB - round(i * self.innerHeightPx/stepcnt)
                self.create_line(self.chartWidth-self.marginR+4, y_coord, self.chartWidth-self.marginR, y_coord, fill=color, tags='axes')  # Y tick
                self.create_text(self.chartWidth-4, y_coord, text=fmts.format(y2min+i*step), fill=color, anchor='e', tags='axes')  # Y label

        innerWidthPx = self.chartWidth - self.marginL - self.marginR
        
        # Draw X and Y axis
        self.create_line(self.marginL, self.chartHeight-self.marginB, self.chartWidth-self.marginR, self.chartHeight-self.marginB, tags='axes')  # X axis
        self.create_line(self.marginL, self.chartHeight-self.marginB, self.marginL, self.marginT, tags='axes')    # Y axis
        self.create_line(self.marginL, self.marginT, self.chartWidth-self.marginR, self.marginT, tags='axes')  # X axis
        self.create_line(self.chartWidth-self.marginR, self.chartHeight-self.marginB, self.chartWidth-self.marginR, self.marginT, tags='axes')    # Y axis

        # Draw X ticks and labels
        xmin = min(x_values)
        xmax = max(x_values)
        if xmax == xmin:
            xmin -= 0.001
            xmax += 0.001
        span = xmax-xmin
        step = span/3 # we want to split the span in min 3 parts, so this is the maximal step size
        p10 = 10**floor(log10(step)) # the power of 10 that is just lower than the step
        ss = step/p10 # this should be a number between 1 and 9.9999
        ss = 5 if ss>=5 else 2 if ss>=2 else 1 # shorten the step to be a multiple of 1, 2 or 5
        step = ss*p10 # this is the new step size, perhaps smaller than the original
        xmin = floor(xmin/step)*step
        xmax =  ceil(xmax/step)*step
        span = xmax-xmin
        stepcnt = round(span/step)
        x_coef_mult = innerWidthPx/span
        x_coef_add = self.marginL - x_coef_mult*xmin
        
        for i in range(stepcnt+1):
            x_coord = self.marginL + round(i * innerWidthPx/stepcnt)
            self.create_line(x_coord, self.chartHeight-self.marginB, x_coord, self.chartHeight-self.marginB+5, tags='axes')  # X tick
            self.create_text(x_coord, self.chartHeight-self.marginB+12, text='{:g}'.format(xmin+i*step), tags='axes')    # X label


        if DEBUG: print('\naxes:', (time.time()-t0)*1000); t0=time.time()

        xx = [x_coef_add + x_coef_mult * v for v in x_values]
        if len(xx)<2:
            return
        
        
        if len(y_bands)>0 or len(y2_bands)>0:
            xxx = []#[xxx0+i for i in range(floor(xx[-1])-floor(xx[0])+1)]
            last=-1
            xt = [0 for _ in xx]
            for i, xi in enumerate(xx):
                if last != floor(xi):
                    last = floor(xi)
                    xt[i] = 1
                    xxx.append(last)
                
        def contract_band(bo):
            bn = [0 for _ in range(len(xxx)*2)]
            itb = iter(bo)
            mi = next(itb); ma = next(itb)
            itx = iter(xt)
            next(itx)
            ni = 0
            for _ in range(1, len(bo)//2):
                vi = next(itb)
                va = next(itb)
                if next(itx) == 0:
                    if mi>vi: mi = vi
                    if ma<va: ma = va
                else:
                    bn[ni] = mi
                    bn[ni+1] = ma
                    ni += 2
                    mi = vi
                    ma = va
            bn[ni] = mi
            bn[ni+1] = ma
            return bn
                    
        def contract_line(bo):
            bn = [0 for _ in range(len(xxx))]
            itb = iter(bo)
            su = next(itb)
            itx = iter(xt)
            next(itx)
            cnt = 1
            ni = 0
            for _ in range(1, len(bo)):
                v = next(itb)
                if next(itx) == 1:
                    bn[ni] = su/cnt
                    ni += 1
                    su = v
                    cnt = 1
                else:
                    su += v
                    cnt += 1
            bn[ni] = su/cnt
            return bn
        
        if DEBUG: print('x axis calc:', (time.time()-t0)*1000); t0=time.time()

        #import time
        for l, line in enumerate(y_bands):
            if len(line) == 0: continue
            line = contract_band(line)
            color = self.colors_pale[l % len(self.colors)]
            #t0=time.time()
            yy = [y_coef_add + y_coef_mult * v for v in line]
            aaa = [v for pair in zip(xxx + xxx[-1::-1], yy[0::2]+yy[-1::-2]) for v in pair]
            #print((time.time()-t0)*1000); t0=time.time()
            self.create_polygon(*aaa, fill=color, outline=color, tags='series') # the create_polygon line is ca 5x slower than the array preparation lines above
            #print('         ', (time.time()-t0)*1000)
        for l, line in enumerate(y2_bands):
            if len(line) == 0: continue
            line = contract_band(line)
            color = self.colors_pale[(l+len(y_values)) % len(self.colors)]
            yy = [y2_coef_add + y2_coef_mult * v for v in line]
            aaa = [v for pair in zip(xxx + xxx[-1::-1], yy[0::2]+yy[-1::-2]) for v in pair]
            self.create_polygon(*aaa, fill=color, outline=color, tags='series')
            
        if DEBUG: print('bands:', (time.time()-t0)*1000); t0=time.time()
        
        for l, line in enumerate(y_values):
            color = self.colors[l % len(self.colors)]
            if len(y_bands)>l and len(y_bands[l])>0:
                line = contract_line(line)
                yy = [y_coef_add + y_coef_mult * v for v in line]
                aaa = [v for pair in zip(xxx, yy) for v in pair]
            else:
                yy = [y_coef_add + y_coef_mult * v for v in line]
                aaa = [v for pair in zip(xx, yy) for v in pair]
            self.create_line(*aaa, fill=color, tags='series')
        for l, line in enumerate(y2_values):
            color = self.colors[(l+len(y_values)) % len(self.colors)]
            if len(y2_bands)>l and len(y2_bands[l])>0:
                line = contract_line(line)
                yy = [y2_coef_add + y2_coef_mult * v for v in line]
                aaa = [v for pair in zip(xxx, yy) for v in pair]
            else:
                yy = [y2_coef_add + y2_coef_mult * v for v in line]
                aaa = [v for pair in zip(xx, yy) for v in pair]
            #print((time.time()-t0)*1000)
            self.create_line(*aaa, fill=color, tags='series')
            #print('         ', (time.time()-t0)*1000)

        if DEBUG: print('lines:', (time.time()-t0)*1000); t0=time.time()
    

        for i in range(len(y_legend)):
            color = self.colors[i % len(self.colors)]
            self.create_text(4, 12+i*13, text=y_legend[i], fill=color, anchor='w', tags='axes')  
        for i in range(len(y2_legend)):
            color = self.colors[(i+len(y_values)) % len(self.colors)]
            self.create_text(self.chartWidth-4, 12+i*13, text=y2_legend[i], fill=color, anchor='e', tags='axes')  # Y2 legend
        #print((time.time()-t0)*1000)
        
        if DEBUG: print('legend:', (time.time()-t0)*1000); t0=time.time()



if __name__ == '__main__':
    root = tki.Tk()
    root.title('chart test')
    root.geometry('350x650')
    chart = Chart(root, 350, 650, 'Time before now / min')
    chart.place(x=0, y= 0)
    chart.draw([1, 2, 3, 4, 5], [[1,2,2,3,1]], y_bands=[[-1,3, 1,3, 0,3, 1,4, -1,2]])
    import random
    import time
    npts = 20000
    curvecnt = 5
    x = [i for i in range(npts)]
    y = [[random.random()+i*10+2 for _ in range(npts)] for i in range(curvecnt)]
    b = [[item for row in [[-random.random()-1+v, random.random()+1+v] for v in yi] for item in row] for yi in y]
    y2= [[k+5 for k in y[i]] for i in range(curvecnt)]
    b2= [[k+5 for k in b[i]] for i in range(curvecnt)]
    t00 = time.time()
    chart.draw(x, y, y2)                                # 34 ms for 10x2000 pts
    print((time.time()-t00)*1000, 'ms for', curvecnt*2,'x', npts,'pts')
    chart.clear()
    t00 = time.time()
    chart.draw(x, y, y2, y_bands=b, y2_bands=b2)        # 92 ms for 10x2000 pts plus bands
    print((time.time()-t00)*1000, 'ms for', curvecnt*2,'x', npts,'pts plus bands')
    root.mainloop()
