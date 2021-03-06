import numpy as np
import pandas as pd
from astropy import units as u
import plotly.graph_objects as go
from astropy.coordinates import SkyCoord
from skimage.transform import downscale_local_mean
import sunpy.map
        
class fake_map:
    def __init__(self,sunpy_map,tickspacing=100,binning=1,bottom_left=None,top_right=None,round=-2):
        '''plot SunPy maps in Plotly. Can input bottom_left and top_right as SkyCoords in map coordinate frame'''
        self.map=sunpy_map
        self.datashape=sunpy_map.data.shape #x- and y- reversed as per usual (thanks FITS)
        self.wcs=sunpy_map.wcs.to_header().tostring()
        self._get_observer()
        self.tickspacing=tickspacing
        self.binning=binning
        self.bottom_left=bottom_left
        self.top_right=top_right
        self.round=round
        self.bin_data()
        self.get_axis_limits()
        self.get_wcs_grid()
        self.get_tickinfo()
        
    def _get_observer(self):
        ''' get heliographic observer so that SkyCoord can be reconstructed properly'''
        observer=self.map.coordinate_frame.observer
        self.olon=observer.lon.value
        self.olat=observer.lat.value
        self.orad=observer.radius.value
        self.olon_unit=observer.lon.unit.name
        self.olat_unit=observer.lat.unit.name
        self.orad_unit=observer.radius.unit.name
        self.obstime=observer.obstime
        self.obsframe='heliographic_stonyhurst' #is this universally true? I think it is for observer

        
    def bin_data(self):
        if self.binning != 1.:
            self.binned_data=downscale_local_mean(self.map.data, (self.binning,self.binning),clip=True)
    
    def get_axis_limits(self):
        '''get wcs axes limits in pixels. Helps fake the transform'''
        if not self.bottom_left:
            self.bottom_left = self.map.bottom_left_coord
        if not self.top_right:
            self.top_right = self.map.top_right_coord
        #round - have to make new sky coords I think
        self.bottom_left=SkyCoord(np.round(self.bottom_left.Tx.value,-2)*u.arcsec,np.round(self.bottom_left.Ty.value,-2)*u.arcsec,frame=self.map.coordinate_frame)
        self.top_right=SkyCoord(np.round(self.top_right.Tx.value,-2)*u.arcsec,np.round(self.top_right.Ty.value,-2)*u.arcsec,frame=self.map.coordinate_frame)
        try:
            bl=self.map.world_to_pixel(self.bottom_left)
            tr=self.map.world_to_pixel(self.top_right)
            self.xlim=[bl.x.value/self.binning,tr.x.value/self.binning]
            self.ylim=[bl.y.value/self.binning,tr.y.value/self.binning] #would int division be better?
        except ValueError:
            print('')#f"{self.bottom_left} or {self.top_right} is not a SkyCoord!")
    
    def generate_coords(self,X,Y):
        '''where is this being slow? meshgrid? '''
        cc=[self.map.pixel_to_world(x*u.pix,y*u.pix) for x,y in zip(X,Y)] #list of skycoords
        xtv=[int(c.Ty.value) for c in cc]
        ytv=[int(c.Tx.value) for c in cc]
        return np.meshgrid(xtv,ytv,copy=False)
    
    def get_wcs_grid(self):
        '''Outputs numpy array for use in plotly's customdata argument. Basically this will trick the hovertext into displaying world coords instead of pixel coords
        Accurate to within binning/2 pixels (could add them back eventually) '''
        x=list(np.linspace(0,self.datashape[1],self.datashape[1]//self.binning))
        y=list(np.linspace(0,self.datashape[0],self.datashape[0]//self.binning))
        xg,yg=self.generate_coords(x,y)
        self.customdata=np.dstack((xg,yg))
    
    def get_tickinfo(self):
        '''gets tick values in pixel coords and labels in wcs coords, depending on desired tick spacing (wcs) and axis boundaries (wcs)'''
        tickrangex=(self.top_right.Ty.value-self.bottom_left.Ty.value)//self.tickspacing+1
        tickrangey=(self.top_right.Tx.value-self.bottom_left.Tx.value)//self.tickspacing+1
        world_tickvalsx=np.linspace(self.bottom_left.Ty.value,self.top_right.Ty.value,int(tickrangex))
        world_tickvalsy=np.linspace(self.bottom_left.Tx.value,self.top_right.Tx.value,int(tickrangey))
        xtv,ytv=[],[]
        for vx,vy in zip(world_tickvalsx,world_tickvalsy):
            cc=self.map.world_to_pixel(SkyCoord(vx*u.arcsec,vy*u.arcsec,frame=self.map.coordinate_frame))
            xtv.append(cc.x.value/self.binning)
            ytv.append(cc.y.value/self.binning)
        self.xtickvals=xtv
        self.ytickvals=ytv
        self.ticktextx=[str(int(l)) for l in world_tickvalsx]
        self.ticktexty=[str(int(l)) for l in world_tickvalsy]
        
    def _cleanup(self):
        '''for use in display app... get rid of original data, use only binned, get rid of other stuff no longer needed '''
        del self.map
        del self.datashape
        del self.tickspacing
        del self.bottom_left
        del self.top_right
        del self.round
        
    def _flatten(self):
        flattened_dict={}
        for k,v in self.__dict__.items():
            flattened_dict[k]=[v]
        return flattened_dict
        
    def to_dataframe(self):
        df=pd.DataFrame(self._flatten())
        return df
        
    def plot_fake_heatmap(self,zmin=None,zmax=None,log=False):
        try:
            plotdata=self.binned_data
        except AttributeError:
            plotdata=self.map.data
        
        if log: plotdata=np.log10(plotdata)
           
        if not zmin: zmin=np.min(plotdata)
        if not zmax: np.max(plotdata)

        fig = go.Figure()

        fig.add_trace(go.Heatmap(z=plotdata,zmin=zmin,zmax=zmax,customdata=self.customdata,hovertemplate='x: %{customdata[0]}"<br>y: %{customdata[1]}"<br>%{z} DN/s <extra></extra>'))
        fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=self.xtickvals,ticktext=self.ticktextx,showgrid=False,zeroline=False)
        fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=self.ytickvals,ticktext=self.ticktexty,showgrid=False,zeroline=False,scaleanchor = "x",scaleratio = 1)
        fig.update_layout(title=self.map.meta['date-obs'],xaxis_range=self.xlim,yaxis_range=self.ylim) #,autosize=False,height=650,width=550,margin=dict(l=50,r=50,b=100,t=100,pad=4)
        return fig
        
    def plot_fake_image(self,zmin=None,zmax=None,log=False):
        '''to be completed - set as image in background of plotly scatter (see dem_inspect app for example) '''
        try:
            plotdata=self.binned_data
        except AttributeError:
            plotdata=self.map.data
        
        if log: plotdata=np.log10(plotdata)
           
        if not zmin: zmin=np.min(plotdata)
        if not zmax: np.max(plotdata)

        fig = go.Figure()

        fig.add_trace(go.Heatmap(z=plotdata,zmin=zmin,zmax=zmax,customdata=self.customdata,hovertemplate='x: %{customdata[0]}"<br>y: %{customdata[1]}"<br>%{z} DN/s <extra></extra>'))
        fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=self.xtickvals,ticktext=self.ticktextx,showgrid=False,zeroline=False)
        fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=self.ytickvals,ticktext=self.ticktexty,showgrid=False,zeroline=False,scaleanchor = "x",scaleratio = 1)
        fig.update_layout(title=self.map.meta['date-obs'],xaxis_range=self.xlim,yaxis_range=self.ylim) #,autosize=False,height=650,width=550,margin=dict(l=50,r=50,b=100,t=100,pad=4)
        return fig
