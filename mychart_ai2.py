import tkinter as tki
from math import floor, ceil, log10
import statistics
import tooltip

DEBUG = False

if DEBUG: import time

''' usage:
        self.chart = mychart.Chart(self.master, 350, 350)
        self.chart.place(x=0, y=100)
        self.chart.draw([212e-4, 222e-4, 232e-4, 242e-4, 252e-4], [[2, 4, 6, 8, 16], [1, 3, 5, 7, 9]])
'''

class Chart(tki.Canvas):
    def __init__(self, master, awidth, aheight, x_axis_title = '', legend_style='all', on_save_zoom_proc=None): # legend_style 'all' or 'selected'
        super().__init__(master, width=awidth, height=aheight,  borderwidth=0, bg='white')
        self.chartWidth = awidth
        self.chartHeight = aheight
        self.marginL = self.marginT = self.marginB = self.marginR = 40
        self.colors      = ['red'    , 'blue'   , 'black'  , '#ffaa00', 'green'  , '#ff00ff', '#00aaff', '#aa0000', '#000099', '#006600', '#ee6600', '#777777']
        self.colors_pale = ['#ff8888', '#8888ff', '#888888', '#ffff00', '#44cc44', '#ff88ff', '#88ffff', '#cc8888', '#6666cc', '#44aa44', '#ffaa00', '#aaaaaa']
        self.innerHeightPx= self.chartHeight- self.marginT - self.marginB
        self.tmpcanvas = tki.Canvas(master, width=1, height=1)
        self.tmptext = self.tmpcanvas.create_text(0, 0, text='')
        self.create_text(awidth / 2, aheight - 14, text=x_axis_title, anchor='center', tags='const')  # Y label
        
        self.mousedown_x = 0
        self.mousedown_y = 0
        self.scrolled_axis = 'x'
        self.x_coef_mult = 1.0
        self.y_coef_mult = []
        self.y2_coef_mult = []
        self.x_coef_add = 0.0
        self.y_coef_add = []
        self.y2_coef_add = []
        self.x_minmax: tuple[float, float]  = (0.0, 1.0)
        self.y_minmax: list[tuple[float,float]] = [] #list[str] | list[tuple[float,float]] | tuple[float, float] | str = (0.0, 1.0)
        self.y2_minmax: list[tuple[float,float]] = [] #list | tuple[float, float] | str = (0.0, 1.0)
        self.selected_line_ind = -1
        self.selected_line_ind2 = -1
        
        self.legend_style = legend_style # or 'all' or 'selected'
        
        self.inner_canvas = tki.Canvas(self,  borderwidth=0, bg='white', closeenough=4, cursor='left_ptr')
        #self.inner_canvas.place(x=self.marginL, y=self.marginT, width=awidth-self.marginL-self.marginR, height=aheight-self.marginT-self.marginB)
        self.bind("<Button-1>", self.mousedown)
        #self.bind("<Button-3>", self.mousedown)
        self.bind("<B1-Motion>", self.drag_axis)
        #self.bind("<B3-Motion>", self.drag_translate)
        self.bind("<Motion>", self.mousemove)
        self.inner_canvas.bind("<B1-Motion>", self.inner_drag)
        self.inner_canvas.bind("<Button-1>", self.inner_mousedown)
        self.inner_canvas.bind("<ButtonRelease-1>", self.inner_mouseup)
        
        self.btn_reset = tki.Button(self, text='↶', command=self.reset_zoom, cursor='left_ptr')
        self.btn_reset.place(x=-30, y=self.chartHeight-16, width=16, height=16)
        tooltip.ToolTip(self.btn_reset, 'Undo zoom/move')
        
        self.btn_save = tki.Button(self, text='💾', command=self.save_zoom, cursor='left_ptr')
        self.btn_save.place(x=-30, y=self.chartHeight-16, width=16, height=16)
        tooltip.ToolTip(self.btn_save, 'Save current zoom/move')
        
        self.cursor = 'left_ptr'
        
        self.zooming = False
        self.has_custom_zoom = False
        
        self.on_save_zoom_proc = on_save_zoom_proc
        
        
        
    def drag_axis(self, ev):
        # Scaling:
        # dragged from self.mousedown_x (p1) to ev.x (p2) while keeping either the min or max shown.
        # The dragged end shifts by the dragged amount, the other end stays.
        # p = a + m*v
        # For 3 points A (fixed end), B (dragged point) and C (moved end):
        # pA=a+m*vA, pA=a2+m2*vA, pB=a+m*vB, pB2=a2+m2*vB, pC=a+m*vC, pC=a2+m2*vC2
        # we are looking for vC2 and we have vA, pB, pB2, vC, a and m.
        # pC-pB2=(vC2-vB)*m2,   (vC2-vB)=(pC-pB2)/m2,    pA-pB2=(vA-vB)*m2,   (vC2-vB)=(pC-pB2)*(vA-vB)/(pA-pB2),
        # vC2 = (pB-a)/m + (a+m*vC - pB2)*(vA - (pB-a)/m)  / (a+m*vA - pB2)
        #     = vC + (pB-pB2)*(vA-vC)/(vA*m+a-pB2)
        # Here the last pB2 should come from the inner drawing canvas, but we have instead ev.x/y which come from the external axes;
        # the inner canvas is placed at marginL/T+2, so  pB2=ev.x-self.marginL-2:
        if self.scrolled_axis == 'sxmin' or self.scrolled_axis == 'sxmax': # drag along x:
            d_pixels = self.mousedown_x - ev.x
            if d_pixels == 0:
                return
            if self.scrolled_axis == 'sxmin':
                divby = self.x_minmax[1]*self.x_coef_mult+self.x_coef_add-ev.x    +self.marginL+2
                if divby < 2: return
                self.x_minmax = (self.x_minmax[0]+d_pixels*(self.x_minmax[1]-self.x_minmax[0])/divby, self.x_minmax[1])
            else:
                divby = self.x_minmax[0]*self.x_coef_mult+self.x_coef_add-ev.x    +self.marginL+2
                if divby > -2: return
                self.x_minmax = (self.x_minmax[0], self.x_minmax[1]+d_pixels*(self.x_minmax[0]-self.x_minmax[1])/divby)
        elif self.scrolled_axis == 'symin' or self.scrolled_axis == 'symax': # drag along y:
            d_pixels = self.mousedown_y - ev.y
            if d_pixels == 0:
                return
            for i in range(len(self.y_values)):
                if self.selected_line_ind<0 or i==self.selected_line_ind:
                    if self.scrolled_axis == 'symin':
                        divby = self.y_minmax[i][1]*self.y_coef_mult[i]+self.y_coef_add[i]-ev.y       +self.marginT+2
                        if divby > -2: return
                        self.y_minmax[i] = (self.y_minmax[i][0]+d_pixels*(self.y_minmax[i][1]-self.y_minmax[i][0])/divby, self.y_minmax[i][1])
                    else:
                        divby = self.y_minmax[i][0]*self.y_coef_mult[i]+self.y_coef_add[i]-ev.y       +self.marginT+2
                        if divby < 2: return
                        self.y_minmax[i] = (self.y_minmax[i][0], self.y_minmax[i][1]+d_pixels*(self.y_minmax[i][0]-self.y_minmax[i][1])/divby)
        elif self.scrolled_axis == 'sy2min' or self.scrolled_axis == 'sy2max': # drag along y2:
            d_pixels = self.mousedown_y - ev.y
            if d_pixels == 0:
                return
            for i in range(len(self.y2_values)):
                if self.selected_line_ind2<0 or i==self.selected_line_ind2:
                    if self.scrolled_axis == 'sy2min':
                        divby = self.y2_minmax[i][1]*self.y2_coef_mult[i]+self.y2_coef_add[i]-ev.y      +self.marginT+2
                        if divby > -2: return
                        self.y2_minmax[i] = (self.y2_minmax[i][0]+d_pixels*(self.y2_minmax[i][1]-self.y2_minmax[i][0])/divby, self.y2_minmax[i][1])
                    else:
                        divby = self.y2_minmax[i][0]*self.y2_coef_mult[i]+self.y2_coef_add[i]-ev.y      +self.marginT+2
                        if divby < 2: return
                        self.y2_minmax[i] = (self.y2_minmax[i][0], self.y2_minmax[i][1]+d_pixels*(self.y2_minmax[i][0]-self.y2_minmax[i][1])/divby)
        # translating:
        # dragged from self.mousedown_x to ev.x: a change dx_p = ev.x - self.mousedown_x that corresponds to
        # (according to x_px = coef_add + coef_mult*x_v:   v1=(p1-a)/m   v2=(p2-a)/m   v2-v1=(p2-p1)/m=dx_p/m
        elif self.scrolled_axis == 'tx': # drag along x:
            d_pixels = self.mousedown_x - ev.x
            if d_pixels == 0:
                return
            d_v = d_pixels/self.x_coef_mult
            self.x_minmax = (self.x_minmax[0]+d_v, self.x_minmax[1]+d_v)
        elif self.scrolled_axis == 'ty': # drag along y:
            d_pixels = self.mousedown_y - ev.y
            if d_pixels == 0:
                return
            for i in range(len(self.y_values)):
                if self.selected_line_ind<0 or i==self.selected_line_ind:
                    d_v = d_pixels/self.y_coef_mult[i]
                    self.y_minmax[i] = (self.y_minmax[i][0]+d_v, self.y_minmax[i][1]+d_v)
        elif self.scrolled_axis == 'ty2': # drag along y2:
            d_pixels = self.mousedown_y - ev.y
            if d_pixels == 0:
                return
            for i in range(len(self.y2_values)):
                if self.selected_line_ind2<0 or i==self.selected_line_ind2:
                    d_v = d_pixels/self.y2_coef_mult[i]
                    self.y2_minmax[i] = (self.y2_minmax[i][0]+d_v, self.y2_minmax[i][1]+d_v)
        else:
            return
        self.mousedown_x = ev.x
        self.mousedown_y = ev.y
        self.zooming = True
        self.btn_reset.place(x=0)
        self.btn_save.place(x=self.chartWidth-18)
        self._draw()

        
    '''def drag_translate(self, ev):
        #print(ev, ev.x_root, ev.x)
        # dragged from self.mousedown_x to ev.x: a change dx_p = ev.x - self.mousedown_x that corresponds to
        # (according to x_px = coef_add + coef_mult*x_v:   v1=(p1-a)/m   v2=(p2-a)/m   v2-v1=(p2-p1)/m=dx_p/m
        if self.scrolled_axis == 'tx': # drag along x:
            d_pixels = self.mousedown_x - ev.x
            if d_pixels == 0:
                return
            d_v = d_pixels/self.x_coef_mult
            self.x_minmax = (self.x_minmax[0]+d_v, self.x_minmax[1]+d_v)
        elif self.scrolled_axis == 'ty': # drag along y:
            d_pixels = self.mousedown_y - ev.y
            if d_pixels == 0:
                return
            for i in range(len(self.y_values)):
                if self.selected_line_ind<0 or i==self.selected_line_ind:
                    d_v = d_pixels/self.y_coef_mult[i]
                    self.y_minmax[i] = (self.y_minmax[i][0]+d_v, self.y_minmax[i][1]+d_v)
        elif self.scrolled_axis == 'ty2': # drag along y2:
            d_pixels = self.mousedown_y - ev.y
            if d_pixels == 0:
                return
            for i in range(len(self.y2_values)):
                if self.selected_line_ind2<0 or i==self.selected_line_ind2:
                    d_v = d_pixels/self.y2_coef_mult[i]
                    self.y2_minmax[i] = (self.y2_minmax[i][0]+d_v, self.y2_minmax[i][1]+d_v)
        else:
            return
        self.mousedown_x = ev.x
        self.mousedown_y = ev.y
        self.zooming = True
        self.btn_reset.place(x=0)
        self._draw()'''
        
    def mousedown(self, ev):
        self.mousedown_x = ev.x
        self.mousedown_y = ev.y
        self.mousemove(ev)
        '''if ev.y > self.chartHeight - self.marginB:
            self.scrolled_axis = 'x'
            self.scrolled_min  = ev.x<self.chartWidth/2
        elif ev.x < self.marginL:
            self.scrolled_axis = 'y'
            self.scrolled_min  = ev.y>self.chartHeight/2
        else:
            self.scrolled_axis = 'y2'
            self.scrolled_min  = ev.y>self.chartHeight/2
        if ev.y < self.marginT:
            self.scrolled_axis = 'none'
        '''
        '''if ev.x < self.chartWidth/2:
                self.selected_line_ind = (ev.y-8) // 13
            else:
                self.selected_line_ind2= (ev.y-8) // 13
            self._draw()'''
        
    def set_cursor(self, c):
        if self.cursor != c:
            self.configure(cursor=c) # crazy gpu usage if you just do this on each mouse move
            self.cursor = c
        
    def mousemove(self, ev):
        if ev.y < self.marginT:
            self.set_cursor('left_ptr')
            self.scrolled_axis = 'none'
        elif ev.y > self.chartHeight - self.marginB:
            if ev.x > self.chartWidth*3/4:
                self.set_cursor('right_tee') #bottom_side
                self.scrolled_axis = 'sxmax'
            elif ev.x < self.chartWidth/4:
                self.set_cursor('left_tee')
                self.scrolled_axis = 'sxmin'
            else:
                self.set_cursor('sb_h_double_arrow')
                self.scrolled_axis = 'tx'
        elif ev.x < self.marginL or ev.x > self.chartWidth-self.marginR:
            ax = 'y' if ev.x < self.marginL else 'y2'
            if ev.y > self.chartHeight*3/4:
                self.set_cursor('bottom_tee') #bottom_side
                self.scrolled_axis = 's'+ax+'min'
            elif ev.y < self.chartHeight/4:
                self.set_cursor('top_tee')
                self.scrolled_axis = 's'+ax+'max'
            else:
                self.set_cursor('sb_v_double_arrow')
                self.scrolled_axis = 't'+ax
        else:
            self.set_cursor('left_ptr')
            self.scrolled_axis = 'none'

        
    def inner_drag(self, ev):
        self.inner_canvas.coords(self.zoomrect, self.mousedown_x, self.mousedown_y, ev.x, ev.y)
        if abs(self.mousedown_x-ev.x)>5 or abs(self.mousedown_y-ev.y)>5:
            self.cancel_select = True


    def inner_mousedown(self, ev):
        self.mousedown_x = ev.x
        self.mousedown_y = ev.y
        self.zoomrect = self.inner_canvas.create_rectangle(ev.x, ev.y, ev.x+5, ev.y+5, dash=(5,), tags='zoom')
        self.cancel_select = False

    def inner_mouseup(self, ev):
        self.inner_canvas.delete('zoom')
        x0 = min(self.mousedown_x, ev.x)
        x1 = max(self.mousedown_x, ev.x)
        y1 = min(self.mousedown_y, ev.y)
        y0 = max(self.mousedown_y, ev.y)
        if x1-x0 < 6 or y0-y1 < 6:
            return
        # v=(p-a)/m
        self.x_minmax = ((x0-self.x_coef_add)/self.x_coef_mult, (x1-self.x_coef_add)/self.x_coef_mult)
        for i in range(len(self.y_values)):
            self.y_minmax[i] = ((y0-self.y_coef_add[i])/self.y_coef_mult[i], (y1-self.y_coef_add[i])/self.y_coef_mult[i])
        for i in range(len(self.y2_values)):
            self.y2_minmax[i] = ((y0-self.y2_coef_add[i])/self.y2_coef_mult[i], (y1-self.y2_coef_add[i])/self.y2_coef_mult[i])
        self.zooming = True
        self.btn_reset.place(x=0)
        self.btn_save.place(x=self.chartWidth-18)
        self._draw()
        

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
        
    def reset_zoom(self):
        self.x_minmax = self.x_minmax_orig[:]
        self.y_minmax = self.y_minmax_orig[:]
        self.y2_minmax = self.y2_minmax_orig[:]
        self.zooming = False
        self.btn_reset.place(x=-30)
        self.btn_save.place(x=-30)
        self._draw()

    def save_zoom(self):
        self.x_minmax_orig = self.x_minmax[:]
        self.y_minmax_orig = self.y_minmax[:]
        self.y2_minmax_orig = self.y2_minmax[:]
        self.zooming = False
        self.btn_reset.place(x=-30)
        self.btn_save.place(x=-30)
        self.has_custom_zoom = True
        if not self.on_save_zoom_proc is None:
            self.on_save_zoom_proc(self.x_minmax, self.y_minmax, self.y2_minmax)


    def _calcMinMaxYAxes(self, lines, bands, minmax, si, prevlinecnt, left, i0, i1):
        # Draw Y ticks and labels:
        if len(lines) == 0:
            return 
        if si<0 or si>=len(lines): si = 0
        if isinstance(minmax, tuple) and minmax[0] != minmax[1]: # a single, given min,max pair
            ymin = minmax[0]
            ymax = minmax[1]
            if ymax == ymin: ymin -= 0.001; ymax += 0.001
            minmax = [(ymin, ymax) for _ in range(len(lines))]
        elif isinstance(minmax, list): # already separate min,max for each curve
            for i, line in enumerate(lines):
                if not isinstance(minmax[i], tuple) or minmax[i][0]==minmax[i][1]: # separate 'auto' min,max; if already explicit min,max, do nothing
                    ymin = min(line[i0:i1])
                    ymax = max(line[i0:i1])
                    if len(bands)>i and len(bands[i])>0 and len(bands[i][0])>0:
                        ymin = min(ymin, min(bands[i][0][i0:i1]))
                        ymax = max(ymax, max(bands[i][1][i0:i1]))
                    if ymax == ymin: ymin -= 0.001; ymax += 0.001
                    minmax[i] = (ymin, ymax)
            ymin, ymax = minmax[si]
        else: # minmax == 'auto': a single 'auto' min,max
            ymin = min(min(y[i0:i1]) for y in lines if len(y)>0)
            ymax = max(max(y[i0:i1]) for y in lines if len(y)>0)
            for band in bands:
                if len(band)>0 and len(band[0])>0:
                    ymin = min(ymin, min(band[0][i0:i1]))
                    ymax = max(ymax, max(band[1][i0:i1]))
            if ymax == ymin: ymin -= 0.001; ymax += 0.001
            minmax = [(ymin, ymax) for _ in range(len(lines))]
        coef_mult= [     self.innerHeightPx/(mi-ma) for mi,ma in minmax]
        coef_add = [- ma*self.innerHeightPx/(mi-ma) for mi,ma in minmax]
        mul = coef_mult[si]
        span = ymax-ymin
        step = span/4 # we want to split the span in min 4 parts, so this is the maximal step size
        l10 = floor(log10(step))
        p10 = 10**l10 # the power of 10 that is just lower than the step
        ss = step/p10 # this should be a number between 1 and 9.9999
        ss = 5 if ss>=5 else 2 if ss>=2 else 1 # shorten the step to be a multiple of 1, 2 or 5
        step = ss*p10 # this is the new step size, perhaps smaller than the original
        color = self.colors[(prevlinecnt+si) % len(self.colors)]
        digits = max(0, -l10)
        fmts = '{:.'+str(digits)+'f}'
        v0 = ceil(ymin/step)*step
        stepcnt = floor((span-v0+ymin)/step)
        textwid = self.getTextWidth(fmts, v0, v0+step*stepcnt)
        if left:
            self.marginL = textwid+8
            self.y_minmax = minmax
            self.y_coef_mult = coef_mult
            self.y_coef_add = coef_add
        else:
            self.marginR = textwid+8
            self.y2_minmax = minmax
            self.y2_coef_mult = coef_mult
            self.y2_coef_add = coef_add
        for i in range(stepcnt + 1):
            v = v0+i*step
            y_coord = self.chartHeight-self.marginB- 2 + (v-ymin)*mul # 2 was y_xtra_margin
            if left:
                self.create_line(self.marginL-4, y_coord, self.marginL, y_coord, fill=color, tags='axes')  # Y tick
                self.create_text(self.marginL-8, y_coord, text=fmts.format(v), fill=color, tags='axes', anchor='e')  # Y label
            else:
                self.create_line(self.chartWidth-self.marginR+4, y_coord, self.chartWidth-self.marginR, y_coord, fill=color, tags='axes')  # Y2 tick
                self.create_text(self.chartWidth-4, y_coord, text=fmts.format(v), fill=color, anchor='e', tags='axes')  # Y2 label
            
        
    def draw(self,
             x_values,
             y_values,
             y2_values=None,
             y_legend=None,
             y2_legend=None,
             y_bands=None,
             y2_bands=None,
             x_minmax=(0.0,0.0),
             y_minmax=(0.0,0.0),
             y2_minmax=(0.0,0.0)):
        self.x_values = x_values
        self.y_values = y_values
        self.y2_values = y2_values if not y2_values is None else []
        self.y_legend = y_legend   if not y_legend  is None else []
        self.y2_legend = y2_legend if not y2_legend is None else []
        self.y_bands = y_bands     if not y_bands   is None else []
        self.y2_bands = y2_bands   if not y2_bands  is None else []
        if self.y_legend == 'auto':
            self.y_legend = ['Line '+str(i) for i in range(len(self.y_values))]
        if self.y2_legend == 'auto':
            self.y2_legend = ['Line '+str(i+len(self.y_values)) for i in range(len(self.y2_values))]
        if self.legend_style == 'all':
            self.marginT = 18 + 13*max(len(self.y_legend), len(self.y2_legend))
        else:
            self.marginT = 18 + 13*(1 if len(self.y_legend)>0 or len(self.y2_legend)>0 else 0)
        if not self.zooming and not self.has_custom_zoom:
            self.x_minmax = x_minmax
            self.y_minmax = y_minmax
            self.y2_minmax = y2_minmax
        if not self.has_custom_zoom: #not hasattr(self, 'x_minmax_orig'):
            #print('setting orig')
            self.x_minmax_orig = x_minmax
            self.y_minmax_orig = y_minmax
            self.y2_minmax_orig = y2_minmax
        self._draw()
        
    
    def _draw(self):
        if DEBUG: t0 = time.time(); t00 = t0

        x_xtra_margin = 2
        y_xtra_margin = 2
        self.innerHeightPx = self.chartHeight - self.marginT - self.marginB - 2*y_xtra_margin-1
        
        self.delete('axes')
        self.delete('series')
        self.inner_canvas.delete('series')
        
        if self.x_minmax[0] == self.x_minmax[1]: # == 'auto':
            xmin = min(self.x_values)
            xmax = max(self.x_values)
            self.x_minmax = (xmin, xmax)
        else:
            xmin = self.x_minmax[0]
            xmax = self.x_minmax[1]
        if xmax == xmin:
            xmin -= 0.001
            xmax += 0.001

        i0 = len(self.x_values)
        i1 = 0
        for i, xi in enumerate(self.x_values):
            if xi >= xmin:
                #print('i0, xi', i, xi)
                i0 = max(i-1, 0)
                break
        for i, xi in enumerate(reversed(self.x_values)):
            if xi <= xmax:
                #print('i1, xi', i, xi)
                i1 = min(len(self.x_values)-i+1, len(self.x_values))
                break

        self._calcMinMaxYAxes(self.y_values , self.y_bands , self.y_minmax , self.selected_line_ind ,                  0, True , i0, i1)
        self._calcMinMaxYAxes(self.y2_values, self.y2_bands, self.y2_minmax, self.selected_line_ind2, len(self.y_values), False, i0, i1)

        innerWidthPx = self.chartWidth - self.marginL - self.marginR - 2*x_xtra_margin-1
        self.inner_canvas.place(x=self.marginL+x_xtra_margin, y=self.marginT+y_xtra_margin, width=innerWidthPx+2, height=self.innerHeightPx+2)
        
        # Draw X and Y axis
        self.create_line(self.marginL, self.chartHeight-self.marginB, self.chartWidth-self.marginR, self.chartHeight-self.marginB, tags='axes')  # X axis
        self.create_line(self.marginL, self.chartHeight-self.marginB, self.marginL, self.marginT, tags='axes')    # Y axis
        self.create_line(self.marginL, self.marginT, self.chartWidth-self.marginR, self.marginT, tags='axes')  # X axis
        self.create_line(self.chartWidth-self.marginR, self.chartHeight-self.marginB, self.chartWidth-self.marginR, self.marginT, tags='axes')    # Y axis

        # Draw X ticks and labels
        span = xmax-xmin
        step = span/3 # we want to split the span in min 3 parts, so this is the maximal step size
        p10 = 10**floor(log10(step)) # the power of 10 that is just lower than the step
        ss = step/p10 # this should be a number between 1 and 9.9999
        ss = 5 if ss>=5 else 2 if ss>=2 else 1 # shorten the step to be a multiple of 1, 2 or 5
        step = ss*p10 # this is the new step size, perhaps smaller than the original
        self.x_coef_mult = innerWidthPx/span
        self.x_coef_add =  - self.x_coef_mult*xmin # + self.marginL + x_xtra_margin
        v0 = ceil(xmin/step)*step
        stepcnt = floor((span-v0+xmin)/step)
        
        for i in range(stepcnt+1):
            v = v0+i*step
            x_coord = self.marginL + x_xtra_margin + (v-xmin)*self.x_coef_mult # round(i * innerWidthPx/stepcnt)
            self.create_line(x_coord, self.chartHeight-self.marginB, x_coord, self.chartHeight-self.marginB+5, tags='axes')  # X tick
            self.create_text(x_coord, self.chartHeight-self.marginB+12, text='{:g}'.format(v), tags='axes')    # X label


        if DEBUG: print('\naxes:', (time.time()-t0)*1000); t0=time.time()
        
        #print (xmax, i0, i1)
        xx = [self.x_coef_add + self.x_coef_mult * v for v in self.x_values[i0:i1]]
        if len(xx)<2:
            return
        
        
        xxx = []
        xii = [0]
        last = floor(xx[0])
        for i, xi in enumerate(xx):
            if last != floor(xi):
                xxx.append(last)
                xii.append(i)
                last = floor(xi)
        xxx.append(last)
        xii.append(len(xx))
        #print(xxx, xii)
        
        #print(len(xxx), sum(xt))
        x4 = [k for m in xxx for k in (m, m)]
        if len(x4)<3:
            return
                
        #print(len(x4))
        
        def contract_line_mean(bo):
            return [statistics.fmean(bo[xii[i]:xii[i+1]]) for i in range(len(xii) - 1)]

        def contract_line_mima(bo):
            #return [(min(bo[xii[i]:xii[i+1]]) if i%2==0 else max(bo[xii[i]:xii[i+1]])) for i in range(len(xii) - 1)]
            return [k for i in range(len(xii) - 1) for k in [min(bo[xii[i]:xii[i+1]]), max(bo[xii[i]:xii[i+1]])]]

        def contract_band(mi, ma):
            return ([min(mi[xii[i]:xii[i+1]]) for i in range(len(xii) - 1)],
                    [max(ma[xii[i]:xii[i+1]]) for i in range(len(xii) - 1)])


        if DEBUG: print('x axis calc:', (time.time()-t0)*1000); t0=time.time()

        #import time
        for l, line in enumerate(self.y_bands):
            if len(line) == 0 or len(line[0]) == 0: continue
            line = contract_band(line[0][i0:i1], line[1][i0:i1])
            color = self.colors_pale[l % len(self.colors)]
            #t0=time.time()
            add = self.y_coef_add[l]
            mult= self.y_coef_mult[l]
            yy_mi = [add + mult * v for v in line[0]] 
            yy_ma = [add + mult * v for v in line[1]]
            aaa = [v for pair in zip(xxx + xxx[-1::-1], yy_mi+yy_ma[-1::-1]) for v in pair]
            #print((time.time()-t0)*1000); t0=time.time()
            self.inner_canvas.create_polygon(*aaa, fill=color, outline=color, tags='series') # the create_polygon line is ca 5x slower than the array preparation lines above
            #print('         ', (time.time()-t0)*1000)
        for l, line in enumerate(self.y2_bands):
            if len(line) == 0 or len(line[0]) == 0: continue
            line = contract_band(line[0][i0:i1], line[1][i0:i1])
            color = self.colors_pale[(l+len(self.y_values)) % len(self.colors)]
            add = self.y2_coef_add[l]
            mult= self.y2_coef_mult[l]
            yy_mi = [add + mult * v for v in line[0]] 
            yy_ma = [add + mult * v for v in line[1]]
            aaa = [v for pair in zip(xxx + xxx[-1::-1], yy_mi+yy_ma[-1::-1]) for v in pair]
            self.inner_canvas.create_polygon(*aaa, fill=color, outline=color, tags='series')
            
        if DEBUG: print('bands:', (time.time()-t0)*1000); t0=time.time()
        
        for l, line in enumerate(self.y_values):
            if len(line) == 0: continue
            color = self.colors[l % len(self.colors)]
            add = self.y_coef_add[l]
            mult= self.y_coef_mult[l]
            if len(self.y_bands)>l and len(self.y_bands[l])>0 and len(self.y_bands[l][0])>0:
                line = contract_line_mean(line[i0:i1])
                yy = [add + mult * v for v in line] 
                aaa = [v for pair in zip(xxx, yy) for v in pair]
            else:
                line = contract_line_mima(line[i0:i1])
                yy = [add + mult * v for v in line] 
                aaa = [v for pair in zip(x4, yy) for v in pair]
            ttt = self.inner_canvas.create_line(*aaa, fill=color, tags=['series', 'linesL'],width=4 if l==self.selected_line_ind else 2)
            self.inner_canvas.tag_bind(ttt, "<ButtonRelease-1>", lambda e, a=ttt, ind=l, left=True: self.on_click_line(e, a, ind, left))
            self.inner_canvas.tag_bind(ttt, "<Double-Button-1>", lambda e, a=ttt, ind=l, left=True: self.on_dbl_click_line(e, a, ind, left))
        for l, line in enumerate(self.y2_values):
            if len(line) == 0: continue
            color = self.colors[(l+len(self.y_values)) % len(self.colors)]
            add = self.y2_coef_add[l]
            mult= self.y2_coef_mult[l]
            if len(self.y2_bands)>l and len(self.y2_bands[l])>0 and len(self.y2_bands[l][0])>0:
                line = contract_line_mean(line[i0:i1])
                yy = [add + mult * v for v in line] 
                aaa = [v for pair in zip(xxx, yy) for v in pair]
            else:
                line = contract_line_mima(line[i0:i1])
                yy = [add + mult * v for v in line] 
                aaa = [v for pair in zip(x4, yy) for v in pair]
            #print((time.time()-t0)*1000)
            ttt=self.inner_canvas.create_line(*aaa, fill=color, tags=['series', 'linesR'],width=4 if l==self.selected_line_ind2 else 2)
            self.inner_canvas.tag_bind(ttt, "<ButtonRelease-1>", lambda e, a=ttt, ind=l, left=False: self.on_click_line(e, a, ind, left))
            self.inner_canvas.tag_bind(ttt, "<Double-Button-1>", lambda e, a=ttt, ind=l, left=False: self.on_dbl_click_line(e, a, ind, left))
            #print('         ', (time.time()-t0)*1000)

        if DEBUG: print('lines:', (time.time()-t0)*1000); t0=time.time()    

        for i in range(len(self.y_legend)):
            color = self.colors[i % len(self.colors)]
            bold = 'bold' if self.selected_line_ind == i else ''
            if self.legend_style == 'all':
                self.create_text(4, 12+i*13, text=self.y_legend[i], fill=color, anchor='w', font=('',9,bold) , tags='axes')  #
            elif self.selected_line_ind == i:
                self.create_text(4, 12     , text=self.y_legend[i], fill=color, anchor='w',                    tags='axes') 
        for i in range(len(self.y2_legend)):
            color = self.colors[(i+len(self.y_values)) % len(self.colors)]
            bold = 'bold' if self.selected_line_ind2 == i else ''
            if self.legend_style == 'all':
                self.create_text(self.chartWidth-4, 12+i*13, text=self.y2_legend[i], fill=color, anchor='e', font=('',9,bold) , tags='axes')  # Y2 legend
            elif self.selected_line_ind2== i:
                self.create_text(self.chartWidth-4, 12     , text=self.y2_legend[i], fill=color, anchor='e',                    tags='axes')  # Y2 legend
        #print((time.time()-t0)*1000)
        
        if DEBUG: print('legend:', (time.time()-t0)*1000); t0=time.time()
        if DEBUG: print('total        :', (t0-t00)*1000)
        
        
    def _on_click_line(self, ind, left):
        if self.is_double_click:
            #print('is dbl')
            return
        if left:
            self.selected_line_ind = -1 if self.selected_line_ind == ind else ind
        else:
            self.selected_line_ind2= -1 if self.selected_line_ind2== ind else ind
        self._draw()
        
    def on_click_line(self, _ev, _item, ind, left):
        #print(ev, dir(ev))
        if self.cancel_select:
            return
        self.is_double_click = False
        self.winfo_toplevel().after(200, self._on_click_line, ind, left)
        '''if self.cancel_select:
            return
        if left:
            #self.inner_canvas.itemconfigure('linesL', width=2) # not necess
            self.selected_line_ind = -1 if self.selected_line_ind == ind else ind
        else:
            #self.inner_canvas.itemconfigure('linesR', width=2)# not necess
            self.selected_line_ind2= -1 if self.selected_line_ind2== ind else ind
        #self.inner_canvas.itemconfigure(item, width=4)# not necess
        self._draw()'''

    def on_dbl_click_line(self, _ev, _item, ind, left):
        #print(_ev, _item, ind, left)
        if self.cancel_select:
            return
        if left:
            self.y_minmax[ind]=(0,0)
        else:
            #self.inner_canvas.itemconfigure('linesR', width=2)# not necess
            self.y2_minmax[ind]=(0,0)
        #self.inner_canvas.itemconfigure(item, width=4)# not necess
        self.is_double_click = True
        self.zooming = True
        self.btn_reset.place(x=0)
        self.btn_save.place(x=self.chartWidth-18)
        self._draw()

if __name__ == '__main__':
    root = tki.Tk()
    root.title('chart test')
    root.geometry('350x650')
    chart = Chart(root, 350, 650, 'Time before now / min', legend_style='selected')
    chart.place(x=0, y= 0)
    chart.draw([1, 2, 3, 4, 5], [[1,2,2,3,1]], y_bands=[([-1, 1, 0, 1, -1], [3, 3, 3, 4, 2])], x_minmax=(2.5,3.5))
    import random
    import time
    import math
    npts = 20000
    curvecnt = len(chart.colors)
    x = [i*0.01 for i in range(npts)]
    y = [[random.random()+i*12+2+math.sin(10*j*i/npts)*0.2 for j in range(npts)] for i in range(curvecnt)]
    #b = [[item for row in [[-random.random()-1+v, random.random()+1+v] for v in yi] for item in row] for yi in y]
    b = [([-random.random()-1+v for v in yi], [random.random()+1+v for v in yi]) for yi in y]
    y[4] = []
    b[3] = ([],[])
    y2= [[k+6 for k in y[i]] for i in range(curvecnt)]
    b2= [([k+6 for k in b[i][0]], [k+6 for k in b[i][1]]) for i in range(curvecnt)]
    t000 = time.time()
    chart.draw(x, y, y2, x_minmax=(0,10))                                # 34 ms for 10x2000 pts
    print((time.time()-t000)*1000, 'ms for', curvecnt*2,'x', npts,'pts')
    chart.clear()
    t000 = time.time()
    chart.draw(x, y, y2, y_bands=b, y2_bands=b2, y_minmax=(0,90), y_legend='auto', y2_legend='auto')        # 92 ms for 10x2000 pts plus bands
    print((time.time()-t000)*1000, 'ms for', curvecnt*2,'x', npts,'pts plus bands')
    
    root.mainloop()
