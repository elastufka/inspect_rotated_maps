#import dash_html_components as html

import pandas as pd
import numpy as np
import glob
import os
#from PIL import Image
from matplotlib.colors import Normalize
from matplotlib import cm

from astropy import units as u
from astropy.coordinates import SkyCoord
from plotly.subplots import make_subplots
from datetime import datetime as dt
import plotly.graph_objects as go
from skimage.transform import downscale_local_mean
import sunpy.map
#from fake_maps_plotly import *
from astropy.wcs import WCS
from astropy.wcs.utils import wcs_to_celestial_frame,pixel_to_skycoord, skycoord_to_pixel
#import plotly.express as px
#import dash_html_components as html

#def load_data(datapath='/Users/wheatley/Documents/Solar/STIX/data/'):
#    cwd=os.getcwd()
#    dirs=glob.glob(datapath+"*")
#    orig,rot=[],[]
#    for d in dirs:
#        os.chdir(d)
#        #get maps
#        fitsf=glob.glob("*.fits")
#        if fitsf == []:
#            fitsf=glob.glob("*.json") #temp workaround
#        for f in fitsf:
#            if f.startswith("AIA"):
#                ofile=f
#            elif f.startswith("rotated"):
#                rfile=f
#        #try and find json files of the same names...
#        try:
#            ojson=glob.glob(ofile[:-4]+'json')[0]
#            odf=pd.read_json(ojson)
#        except IndexError:
#            omap=fake_map(sunpy.map.Map(ofile),binning=8,tickspacing=200)
#            omap._cleanup()
#            odf=omap.to_dataframe()
#        try:
#            rjson=glob.glob(rfile[:-4]+'json')[0]
#            rdf=pd.read_json(rjson)#just merge them
#        except IndexError:
#            rmap=fake_map(sunpy.map.Map(rfile),binning=8,tickspacing=200)
#            rmap._cleanup()
#            rdf=rmap.to_dataframe()
#
#        odf['observer']=reconstruct_observer(odf.iloc[0]) #or can take it directly from object
#        rdf['observer']=reconstruct_observer(rdf.iloc[0])
#
#        idx=pd.Index([format_foldername(datapath,d)])
#        odf.set_index(idx,inplace=True,drop=True)
#        rdf.set_index(idx,inplace=True,drop=True)
#        orig.append(odf)
#        rot.append(rdf)
#
#    os.chdir(cwd)
#    all_odf=pd.concat(orig)
#    all_rot=pd.concat(rot)
#    image_df=all_odf.merge(all_rot,left_index=True,right_index=True,suffixes=('_original','_rotated'))
#    return image_df
    
def format_foldername(datapath,fname):
    return fname[len(datapath):-4]+':'+fname[-4:-2]+':'+fname[-2:]
    
def load_example_data():
    orig,rot=[],[]
    jsons=glob.glob('data/*.json')
    for j in jsons:
        odf=pd.read_json(j)
        odf['observer']=reconstruct_observer(odf.iloc[0]) #or can take it directly from object
        idx=pd.Index([format_filename(j)])
        odf.set_index(idx,inplace=True,drop=True)

        if j.startswith('data/AIA'):
            orig.append(odf)
        else:
            rot.append(odf)
    
    all_odf=pd.concat(orig)
    all_rot=pd.concat(rot)
    image_df=all_odf.merge(all_rot,left_index=True,right_index=True,suffixes=('_original','_rotated'))
    return image_df
    
def format_filename(j):
    return j[j.find('_')+1:-9]+':'+j[-9:-7]+':'+j[-7:-5]
    
def reconstruct_observer(row):
    '''Use stored values to reconstruct the heliospheric observer object. Works for input of fake_map object or of dataframe row'''
    olon=row.olon*getattr(u,row.olon_unit) #unit
    olat=row.olat*getattr(u,row.olat_unit) #unit
    orad=row.orad*getattr(u,row.orad_unit) #unit
    observer=SkyCoord(olon,olat,orad,frame=row.obsframe,obstime=row.obstime)
    return observer
    
def image_grid(image_df,target,scale,zmin,zmax):
    '''make the image grid subplots'''
    
    zmin=float(zmin)
    zmax=float(zmax)
    #xmin,ymin=0,0
    cNorm = Normalize(vmin=zmin, vmax=zmax)
    scalarMap  = cm.ScalarMappable(norm=cNorm, cmap='gray' ) #think this one is Plasma
    
    if type(target) != list:
        target=[target]

    rows=1
    fig = make_subplots(rows=rows, cols=2,subplot_titles=["Original","Rotated"])#,shared_xaxes=False,shared_yaxes=False)

    for t in target:
        #xmax,ymax=image_dict[target][binning][target][tidx[0],:,:].shape
        #im_aspect=int(ymax/xmax)
        #img_width=200
        #img_height=200*im_aspect
        #rows_per_method=(int(len(targets)/cols))

        omap=image_df.binned_data_original[t]
        rmap=image_df.binned_data_rotated[t]

        fig.add_trace(go.Heatmap(z=image_df.binned_data_original[t],name=t,zmin=zmin,zmax=zmax,colorscale='Plasma',customdata=image_df.customdata_original[t],hovertemplate='x: %{customdata[0]}"<br>y: %{customdata[1]}"<br>%{z} DN/s <extra></extra>'),row=1,col=1)
        fig.add_trace(go.Heatmap(z=image_df.binned_data_rotated[t],zmin=zmin,zmax=zmax,colorscale='Plasma',customdata=image_df.customdata_rotated[t],hovertemplate='x: %{customdata[0]}"<br>y: %{customdata[1]}"<br>%{z} DN/s <extra></extra>'),row=1,col=2)
        
        fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=image_df.xtickvals_original[t],ticktext=image_df.ticktextx_original[t],showgrid=False,zeroline=False,row=1,col=1,range=image_df.xlim_original[t])
        fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=image_df.ytickvals_original[t],ticktext=image_df.ticktexty_original[t],showgrid=False,zeroline=False,range=image_df.ylim_original[t],scaleanchor = "x",scaleratio = 1,row=1,col=1)
        fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=image_df.xtickvals_rotated[t],ticktext=image_df.ticktextx_rotated[t],showgrid=False,zeroline=False,row=1,col=2,range=image_df.xlim_rotated[t])
        fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=image_df.ytickvals_rotated[t],ticktext=image_df.ticktexty_rotated[t],showgrid=False,zeroline=False,range=image_df.ylim_rotated[t],scaleanchor = "x2",scaleratio = 1,row=1,col=2)

#        for c,m in zip(range(1,3),[omap,rmap]):
#            #print(m.xlim,m.ylim,m.bottom_left,m.top_right,m.ticktextx,m.ticktexty)
#            fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=m.xtickvals,ticktext=m.ticktextx,showgrid=False,zeroline=False,row=1,col=c,range=m.xlim)
#            fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=m.ytickvals,ticktext=m.ticktexty,showgrid=False,zeroline=False,range=m.ylim)#,scaleanchor = "x",scaleratio = 1

        #subrows=range((rows_per_method*j)+1,(rows_per_method+1)*(j+1))
        #print(subrows)
#        for i,(tx,T) in enumerate(zip(tidx,logTin)):
#            c=i % cols +1
#            r=subrows[(i//4)]
#
#            idata=data[tx,:,:]
#            #fig.add_trace(go.Heatmap(z=idata,zauto=False,zmin=zmin, zmax=zmax,name=f"logT = {T:.1f}",colorbar_title='log DEM'), r, c)
#            img = arr_to_PIL(idata,scalarMap)
#            #print(r,c)
#            fig.add_trace(go.Image(z=img),row=r,col=c)
#
#            fig.update_xaxes(showgrid=False,zeroline=False,matches='x',title=f"logT = {T:.1f}", showticklabels=False,row=r,col=c)
#            fig.update_yaxes(showgrid=False,zeroline=False,matches='y',showticklabels=False,row=r,col=c)

        #fig.update_layout(height=500)
    #if timeit:
    #    print("Time to make image grid: ",(dt.now()-start_time).total_seconds())
    return rows,fig

def arr_to_PIL(imdata,scalarMap):
    seg_colors = scalarMap.to_rgba(imdata)
    img = Image.fromarray(np.uint8(seg_colors*255))
    return img
    
#        to_zoom,new_layout=transform_zoom(relayoutData)
#fig['layout'][to_zoom]=new_layout
def transform_zoom(relayoutData,wcs_original,wcs_rotated,observer_original,observer_rotated,binning=8.):
    '''given zoom information for one subplot, figure out the equivalent coordinates and zoom for the other '''
    kk=list(relayoutData.keys())
    zoomed_axis=0 if kk[0][5] == '.' else 2
    wcs0=WCS(wcs_original)
    wcs1=WCS(wcs_rotated)

    if zoomed_axis==0:
        current_wcs=wcs0
        output_wcs=wcs1
        current_observer=observer_original
        output_observer=observer_rotated
        new_layout={'xaxis2':{'range':[]},'yaxis2':{'range':[]}}
        zaxes=['xaxis2','yaxis2']
    else:
        current_wcs=wcs1
        output_wcs=wcs0
        current_observer=observer_rotated
        output_observer=observer_original
        new_layout={'xaxis':{'range':[]},'yaxis':{'range':[]}}
        zaxes=['xaxis','yaxis']
        
    
    outkeys=list(new_layout.keys())
    #transform axis ranges to to WCS
    bottom_left_wcs_noobs=pixel_to_skycoord(relayoutData[kk[0]]*binning,relayoutData[kk[2]]*binning,current_wcs,mode='wcs') #no observer!
    bottom_left_wcs=SkyCoord(bottom_left_wcs_noobs.Tx,bottom_left_wcs_noobs.Ty,frame='helioprojective',observer=current_observer) #add observer
    top_right_wcs_noobs=pixel_to_skycoord(relayoutData[kk[1]]*binning,relayoutData[kk[3]]*binning,current_wcs,mode='wcs')
    top_right_wcs=SkyCoord(top_right_wcs_noobs.Tx,top_right_wcs_noobs.Ty,frame='helioprojective',observer=current_observer) #add observer
    
    #transform from WCS to pixel coords of other subplot
    testcoord=SkyCoord(0*u.arcsec,0*u.arcsec,frame='helioprojective',observer=output_observer,obstime=output_observer.obstime) ##why is observer= None? that messes things up
    #print(testcoord,bottom_left_wcs.obstime)
    bottom_left_wcs_out=bottom_left_wcs.transform_to(testcoord.frame)
    bottom_left_pix=bottom_left_wcs_out.to_pixel(output_wcs)
    top_right_wcs_out=top_right_wcs.transform_to(testcoord.frame)
    top_right_pix=top_right_wcs_out.to_pixel(output_wcs)
    #need to divide by 8....
    
    #print(bottom_left_wcs,top_right_wcs)
    #print(bottom_left_wcs_out,top_right_wcs_out)
    #print(pixel_to_skycoord(bottom_left_pix[0],bottom_left_pix[1],output_wcs),pixel_to_skycoord(top_right_pix[0],top_right_pix[1],output_wcs))
    
    new_layout[outkeys[0]]['range']=[bottom_left_pix[0]//binning,top_right_pix[0]//binning]
    new_layout[outkeys[1]]['range']=[bottom_left_pix[1]//binning,top_right_pix[1]//binning]
    #what to do if it's out of the axis range? or if transformation gives NaN in skycoords? use height/width of rectangle instead
    #print(new_layout)
    
    return zaxes, new_layout
