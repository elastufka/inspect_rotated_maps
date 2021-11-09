#import dash_html_components as html

import pandas as pd
import numpy as np
import glob
import os
#from PIL import Image
from matplotlib.colors import Normalize
from matplotlib import cm,colors

from astropy import units as u
from astropy.coordinates import SkyCoord
from plotly.subplots import make_subplots
from datetime import datetime as dt
from datetime import timedelta as td
import plotly.graph_objects as go
from skimage.transform import downscale_local_mean
import sunpy.map
import sunpy
from fake_maps_plotly import *
from astropy.wcs import WCS
from astropy.wcs.utils import wcs_to_celestial_frame,pixel_to_skycoord, skycoord_to_pixel
import sunpy.net as sn
import plotly.colors
import plotly.express as px
from rotate_coord import *
#from sunpy_map_utils import query_hek
#import plotly.express as px
import dash_html_components as html
import dash_table
from dash_table.Format import Format, Scheme
from PIL import Image

def load_data(datapath='/Users/wheatley/Documents/Solar/STIX/data/'):
    cwd=os.getcwd()
    dirs=glob.glob(datapath+"*")
    orig,rot=[],[]
    newhekdata=[]
    hek_json=glob.glob(datapath+'Event_HEK_SO.json')[0]
    dirs=[d for d in dirs if 'HEK' not in d]
    hekdf=pd.read_json(hek_json)
    
    for d in dirs:
        os.chdir(d)
        #get maps
        fitsf=glob.glob("*.fits")
        if fitsf == []:
            fitsf=glob.glob("*.json") #temp workaround
        for f in fitsf:
            if f.startswith("AIA"):
                ofile=f
            elif f.startswith("rotated"):
                rfile=f
        #try and find json files of the same names...
        try:
            ojson=glob.glob(ofile[:-4]+'json')[0]
            odf=pd.read_json(ojson)
        except IndexError:
            omap=fake_map(sunpy.map.Map(ofile),binning=8,tickspacing=200)
            omap._cleanup()
            odf=omap.to_dataframe()
        try:
            rjson=glob.glob(rfile[:-4]+'json')[0]
            rdf=pd.read_json(rjson)#just merge them
        except IndexError:
            rmap=fake_map(sunpy.map.Map(rfile),binning=8,tickspacing=200)
            rmap._cleanup()
            rdf=rmap.to_dataframe()

        odf['observer']=reconstruct_observer(odf.iloc[0]) #or can take it directly from object
        rdf['observer']=reconstruct_observer(rdf.iloc[0])

        idx=pd.Index([format_foldername(datapath,d)])
        odf.set_index(idx,inplace=True,drop=True)
        rdf.set_index(idx,inplace=True,drop=True)
        orig.append(odf)
        rot.append(rdf)
        
        if idx.values[0] not in hekdf.Event.values: #query HEK for flares corresponding to this time
            print('Updating HEK dataframe for %s' % idx.values[0])
            idx_dt=dt.strptime(idx.values[0],'%Y-%m-%dT%H:%M:%S')
            qdf=query_hek([idx_dt,idx_dt+td(minutes=1)])
            qdf['Event']=[idx.values[0] for i,_ in qdf.iterrows()]
            #print(qdf)
            qdf=rotate_hek_coords(qdf,odf.observer,odf.wcs,rdf.observer,rdf.wcs,binning=odf.binning.iloc[0])
            if qdf.empty:
                qdf=pd.DataFrame({'Event':idx.values[0],'hpc_x':None,'hpc_y':None,'hpc_bbox':None,'hpc_x_px':None,'hpc_y_px':None,'hpc_x_rotated':None,'hpc_y_rotated':None,'x_px_rotated':None,'y_px_rotated':None,'frm_identifier':None,'frm_name':None},index=pd.Index([0]))
            newhekdata.append(qdf)
            
    if newhekdata != []: #re-write HEK json
        newhekdata.append(hekdf)
        hdf=pd.concat(newhekdata)
        hdf.reset_index(drop=True,inplace=True)
        hdf.to_json(hek_json)
        hekdf=hdf
        print(f'Writing to {hek_json}')

    os.chdir(cwd)
    all_odf=pd.concat(orig)
    all_rot=pd.concat(rot)
    image_df=all_odf.merge(all_rot,left_index=True,right_index=True,suffixes=('_original','_rotated'))
    return image_df,hekdf
    
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
    
def image_grid(image_df,hdf,t,scale,zmin,zmax,cscale='Reds'):
    '''make the image grid subplots'''
    
    zmin=float(zmin)
    zmax=float(zmax)
    try:
        colorsc=getattr(px.colors.sequential,cscale.capitalize())
    except AttributeError:
        colorsc=mplcmap_to_plotly(cscale)
    ccolors, scal = plotly.colors.convert_colors_to_same_type(colorsc)
    clow=ccolors[0]
    chigh=ccolors[-1]
    #xmin,ymin=0,0
    cNorm = Normalize(vmin=zmin, vmax=zmax)
    scalarMap  = cm.ScalarMappable(norm=cNorm, cmap='gray' ) #think this one is Plasma
    
    #if type(target) != list:
    #    target=[target]

    rows=1
    fig = make_subplots(rows=rows, cols=2,subplot_titles=[f"{t} Earth POV",f"{t} Solar Orbiter POV"])#,shared_xaxes=False,shared_yaxes=False)

    #for t in target:
        #xmax,ymax=image_dict[target][binning][target][tidx[0],:,:].shape
        #im_aspect=int(ymax/xmax)
        #img_width=200
        #img_height=200*im_aspect
        #rows_per_method=(int(len(targets)/cols))
    omap=np.array(image_df.binned_data_original[t][0])
    #print(type(omap),omap.shape)
    omap[omap==0]=np.nan #mask zeros
    #print(image_df.xlim_original[t])
    #print(image_df.xlim_original[t][t])
    fig.add_trace(go.Heatmap(z=omap,name=t,zmin=zmin,zmax=zmax,colorscale=cscale,customdata=image_df.customdata_original[t],hovertemplate='x: %{customdata[0]}"<br>y: %{customdata[1]}"<br>%{z} DN/s <extra></extra>'),row=1,col=1)
    fig.add_trace(go.Heatmap(z=image_df.binned_data_rotated[t][0],zmin=zmin,zmax=zmax,colorscale=cscale,customdata=image_df.customdata_rotated[t],hovertemplate='x: %{customdata[0]}"<br>y: %{customdata[1]}"<br>%{z} DN/s <extra></extra>'),row=1,col=2)
        
    fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=image_df.xtickvals_original[t],ticktext=image_df.ticktextx_original[t],showgrid=False,zeroline=False,row=1,col=1,range=image_df.xlim_original[t][t])
    fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=image_df.ytickvals_original[t],ticktext=image_df.ticktexty_original[t],showgrid=False,zeroline=False,range=image_df.ylim_original[t][t],scaleanchor = "x",scaleratio = 1,row=1,col=1)
    fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=image_df.xtickvals_rotated[t],ticktext=image_df.ticktextx_rotated[t],showgrid=False,zeroline=False,row=1,col=2,range=image_df.xlim_rotated[t][t])
    fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=image_df.ytickvals_rotated[t],ticktext=image_df.ticktexty_rotated[t],showgrid=False,zeroline=False,range=image_df.ylim_rotated[t][t],scaleanchor = "x2",scaleratio = 1,row=1,col=2)
    
    #overplot HEK events if present
    hek_events=hdf.where(hdf.Event==t).dropna(how='all')
    binning=image_df.binning_original[t]
    if not hek_events.empty:
        #print(hek_events.hpc_x_px,hek_events.hpc_y_px,hek_events.x_px_rotated,hek_events.y_px_rotated)
        marker=dict(size=15,symbol='cross',color=clow,opacity=.5,line=dict(color=chigh,width=2))
        marker2=dict(size=15,symbol='triangle-up',color=chigh,opacity=.5,line=dict(color=clow,width=2))
        cdata0=np.vstack([hek_events.hpc_x,hek_events.hpc_y]) #one too many when CFL involved
        cdata1=np.vstack([hek_events.hpc_x_rotated,hek_events.hpc_y_rotated])
        #htemp0='x: %{customdata[0]}"<br>y: %{customdata[1]}" <extra></extra>'
        #cdata1=np.array(hek_events.hpc_x_r,hek_events.hpc_y)
        #test
        #fig.add_trace(go.Scatter(x=[0],y=[0],marker=marker,name='origin',customdata=np.array([100]),hovertemplate='%{customdata}<br>%{customdata[0]} points!'),row=1,col=1)
        fig.add_trace(go.Scatter(x=hek_events.hpc_x_px,y=hek_events.hpc_y_px,mode='markers',name='AIA Flare',marker=marker,customdata=cdata0.T,hovertemplate='x: %{customdata[0]:.1f}"<br>y: %{customdata[1]:.1f}" <extra></extra>'),row=1,col=1)
        fig.add_trace(go.Scatter(x=hek_events.x_px_rotated,y=hek_events.y_px_rotated,mode='markers',name='AIA Flare',marker=marker,customdata=cdata1.T,hovertemplate='x: %{customdata[0]:.1f}"<br>y: %{customdata[1]:.1f}" <extra></extra>'),row=1,col=2) #need the HPC rotated coords...
        if 'CFL_X_px' in hek_events.keys():
            cdata2=np.hstack([np.array(hek_events['CFL_LOC_X(arcsec)'].iloc[0]),np.array(hek_events['CFL_LOC_Y (arcsec)'].iloc[0])])

            print(cdata2) #still not the correct labels... something's up with the coordinate rotation. lack of reprojection affecting pixel calcualtion? likely
            if not np.isnan(cdata2).all():
                    fig.add_trace(go.Scatter(x=hek_events.CFL_X_px/binning,y=hek_events.CFL_Y_px/binning,mode='markers',name='SO Flare',marker=marker2,customdata=np.vstack([cdata2,cdata2]),hovertemplate='STIX CFL <br>x: %{customdata[0]:.1f}"<br>y: %{customdata[1]:.1f}" <extra></extra>'),row=1,col=2) #be smarter about picking colors, add hovertext info, move legend
    
    fig.update_layout(legend=dict(
        orientation='h',
        yanchor="top",
        y=1.2,
        xanchor="left",
        x=0.01
    ))
       
        #add polygons too once I remember how to deal with those
    
    return rows,fig
    
    
def image_grid_PIL(image_df,hdf,t,scale,zmin,zmax,cscale='Reds'):
    '''make the image grid subplots'''

    zmin=float(zmin)
    zmax=float(zmax)
    try:
        colorsc=getattr(px.colors.sequential,cscale.capitalize())
    except AttributeError:
        colorsc=mplcmap_to_plotly(cscale)
    ccolors, scal = plotly.colors.convert_colors_to_same_type(colorsc)
    clow=ccolors[0]
    chigh=ccolors[-1]
    #xmin,ymin=0,0
    
    #cNorm = Normalize(vmin=zmin, vmax=zmax)
    #scalarMap  = cm.ScalarMappable(norm=cNorm, cmap='gray' ) #think this one is Plasma
    
    #do scaling etc on PIL image
    omap=np.flipud(np.array(image_df.binned_data_original[t][0]))
    img_width,img_height=omap.shape
    omap[omap==0]=np.nan #mask zeros
    resdat = (omap-zmin)/(zmax - zmin)
    oim = Image.fromarray(np.uint8(sunpy.visualization.colormaps.cm.sdoaia1600(np.array(resdat))*255))
    
    rmap=np.flipud(np.array(image_df.binned_data_rotated[t][0]))
    rmap[rmap==None]=np.nan #mask zeros
    resdat = (rmap-zmin)/(zmax - zmin)
    rim = Image.fromarray(np.uint8(sunpy.visualization.colormaps.cm.sdoaia1600(np.array(resdat).astype(float))*255))

    rows=1
    fig = make_subplots(rows=rows, cols=2,subplot_titles=[f"{t} Earth POV",f"{t} Solar Orbiter POV"])#,shared_xaxes=False,shared_yaxes=False)

    #omap=np.array(image_df.binned_data_original[t])
    #print(type(omap),omap.shape)
    #omap[omap==0]=np.nan #mask zeros
    print('previous:',image_df.xlim_original[t])
    print('current: ',image_df.xlim_original[t].iloc[0])
   
    fig.add_trace(
        go.Scatter(
            x=[0, img_width],
            y=[0, img_height],
            mode="markers",
            marker_opacity=0,customdata=image_df.customdata_original[t],hovertemplate='x: %{customdata[0]}"<br>y: %{customdata[1]}"<br>%{z} DN/s <extra></extra>'),row=1,col=1)

    fig.add_trace(
        go.Scatter(
            x=[0, img_width],
            y=[0, img_height],
            mode="markers",
            marker_opacity=0,customdata=image_df.customdata_rotated[t],hovertemplate='x: %{customdata[0]}"<br>y: %{customdata[1]}"<br>%{z} DN/s <extra></extra>'),row=1,col=2)
   
    fig.add_layout_image(
       dict(
           x=0,
           sizex=img_width ,
           y=0,
           sizey=img_height,
           xref="x",
           yref="y",
           opacity=1.0,
           layer="below",
           sizing="stretch",
           source=oim,
           xanchor='left',yanchor='bottom'))
   
    fig.add_layout_image(
       dict(
           x=0,
           sizex=img_width ,
           y=0 ,
           sizey=img_height,
           xref="x2",
           yref="y2",
           opacity=1.0,
           layer="below",
           sizing="stretch",
           source=rim,
           xanchor='left',yanchor='bottom') #this will actually have to be scaled in advance if done this way...
   )
   

#    fig.update_layout(
#       width=img_width ,
#       height=img_height,
#       margin={"l": 0, "r": 0, "t": 0, "b": 0},
#   )
            
    fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=image_df.xtickvals_original[t][0],ticktext=image_df.ticktextx_original[t][0],showgrid=False,zeroline=False,row=1,col=1,range=image_df.xlim_original[t].iloc[0])
    fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=image_df.ytickvals_original[t][0],ticktext=image_df.ticktexty_original[t][0],showgrid=False,zeroline=False,range=image_df.ylim_original[t].iloc[0],scaleanchor = "x",scaleratio = 1,row=1,col=1)
    fig.update_xaxes(title="Helioprojective Longitude (arcsec)",tickmode='array',tickvals=image_df.xtickvals_rotated[t][0],ticktext=image_df.ticktextx_rotated[t][0],showgrid=False,zeroline=False,row=1,col=2,range=image_df.xlim_rotated[t].iloc[0])
    fig.update_yaxes(title="Helioprojective Latitude (arcsec)",tickmode='array',tickvals=image_df.ytickvals_rotated[t][0],ticktext=image_df.ticktexty_rotated[t][0],showgrid=False,zeroline=False,range=image_df.ylim_rotated[t].iloc[0],scaleanchor = "x2",scaleratio = 1,row=1,col=2)

    #overplot HEK events if present
    hek_events=hdf.where(hdf.Event==t).dropna(how='all')
    binning=image_df.binning_original[t]
    if not hek_events.empty:
        #print(hek_events.hpc_x_px,hek_events.hpc_y_px,hek_events.x_px_rotated,hek_events.y_px_rotated)
        marker=dict(size=15,symbol='cross',color=clow,opacity=.5,line=dict(color=chigh,width=2))
        marker2=dict(size=15,symbol='triangle-up',color=chigh,opacity=.5,line=dict(color=clow,width=2))
        cdata0=np.vstack([hek_events.hpc_x,hek_events.hpc_y]) #one too many when CFL involved
        cdata1=np.vstack([hek_events.hpc_x_rotated,hek_events.hpc_y_rotated])
        #htemp0='x: %{customdata[0]}"<br>y: %{customdata[1]}" <extra></extra>'
        #cdata1=np.array(hek_events.hpc_x_r,hek_events.hpc_y)
        #test
        #fig.add_trace(go.Scatter(x=[0],y=[0],marker=marker,name='origin',customdata=np.array([100]),hovertemplate='%{customdata}<br>%{customdata[0]} points!'),row=1,col=1)
        fig.add_trace(go.Scatter(x=hek_events.hpc_x_px,y=hek_events.hpc_y_px,mode='markers',name='AIA Flare',marker=marker,customdata=cdata0.T,hovertemplate='x: %{customdata[0]:.1f}"<br>y: %{customdata[1]:.1f}" <extra></extra>'),row=1,col=1)
        fig.add_trace(go.Scatter(x=hek_events.x_px_rotated,y=hek_events.y_px_rotated,mode='markers',name='AIA Flare',marker=marker,customdata=cdata1.T,hovertemplate='x: %{customdata[0]:.1f}"<br>y: %{customdata[1]:.1f}" <extra></extra>'),row=1,col=2) #need the HPC rotated coords...
        if 'CFL_X_px' in hek_events.keys():
            cdata2=np.hstack([np.array(hek_events['CFL_LOC_X(arcsec)'].iloc[0]),np.array(hek_events['CFL_LOC_Y (arcsec)'].iloc[0])])

            print(cdata2) #still not the correct labels... something's up with the coordinate rotation. lack of reprojection affecting pixel calcualtion? likely
            if not np.isnan(cdata2).all():
                    fig.add_trace(go.Scatter(x=hek_events.CFL_X_px/binning,y=hek_events.CFL_Y_px/binning,mode='markers',name='SO Flare',marker=marker2,customdata=np.vstack([cdata2,cdata2]),hovertemplate='STIX CFL <br>x: %{customdata[0]:.1f}"<br>y: %{customdata[1]:.1f}" <extra></extra>'),row=1,col=2) #be smarter about picking colors, add hovertext info, move legend

    fig.update_layout(legend=dict(
        orientation='h',
        yanchor="top",
        y=1.2,
        xanchor="left",
        x=0.01
    ))
       
        #add polygons too once I remember how to deal with those

    return rows,fig
    

def mplcmap_to_plotly(cmname:str, pl_entries:int=255):
    cmap=sunpy.visualization.colormaps.cmlist[cmname]
    
    cmap_rgb = []
    norm = colors.Normalize(vmin=0, vmax=255)

    for i in range(0, 255):
           k = colors.colorConverter.to_rgb(cmap(norm(i)))
           cmap_rgb.append(k)

    h = 1.0/(pl_entries-1)
    pl_colorscale = []

    for k in range(pl_entries):
        C = list(map(np.uint8, np.array(cmap_rgb[k])*255))
        pl_colorscale.append([k*h, 'rgb'+str((C[0], C[1], C[2]))])

    return pl_colorscale

    
def hek_events_only(hdf,target):
    '''smaller plot method for testing with Flask '''
    hek_events=hdf.where(hdf.Event==target).dropna(how='all')
    #etitles=[e for e in hek_events.Event]
    #nevents=len(etitles)

    pdata=hek_events[['Event','hpc_x','hpc_y','frm_name','fl_goescls','gs_thumburl','fl_peakflux','fl_peakfluxunit']].to_dict()
    
    
    return pdata
    
def hek_images(hdf,target):
    '''if there are events from HEK, display thumbnail images in figure below main fig, along with flare info in a Div or table '''
    hek_events=hdf.where(hdf.Event==target).dropna(how='all')
    etitles=[e for e in hek_events.Event]
    nevents=len(etitles)

    children=[html.H3("Flare Info")]
    headers,images,aiac,goesc,peakfl,imlink=[],[],[],[],[],[]
    
    #flare info
#    dec= Format(precision=2,scheme=Scheme.fixed)
#    formats = [dec,dec,dec,None,dec]
#    ntypes=['numeric','numeric','numeric','text','numeric']
#    formats = [dec,dec,dec,None,dec]
#    datacols=["frm_name","hpc_x","hpc_y","fl_goescls","fl_peakflux"]
#    infotable=dash_table.DataTable(id='table',
#        columns=[{'name':i,'id':i,'type':t,'format':f} for i,t,f in zip(datacols,ntypes,formats)],
#        data=hek_events.to_dict('records'),style_as_list_view=True,style_cell={'textAlign': 'left'})
#doesn't obey dbc themes yet, sad.
    
    for i,row in hek_events.iterrows():
        #headers
        head=html.Th(row.frm_name)
        headers.append(head)
        headers.append(html.Th('',style={'width':'10px'}))

        #images
        im=html.Img(src=row.gs_thumburl,width=250,height=350)
        images.append(html.Td(im))
        images.append(html.Td('',style={'width':'10px'}))
        #coords
        ctext=f'({row.hpc_x:.2f}",{row.hpc_y:.2f}")'
        aiac.append(html.Td([html.B("AIA coordinates: "),ctext]))
        aiac.append(html.Td('',style={'width':'10px'}))
        #goes class
        gtext=f'{row.fl_goescls}'
        goesc.append(html.Td([html.B('GOES class: '),gtext]))
        goesc.append(html.Td('',style={'width':'10px'}))
        #peak flux
        ftext=f'{row.fl_peakflux:.2f} {row.fl_peakfluxunit}'
        peakfl.append(html.Td([html.B("Peak Flux: "),ftext]))
        peakfl.append(html.Td('',style={'width':'10px'}))
        #high-res image
        imlink.append(html.Td(html.A("high-resolution image",href=row.gs_imageurl)))
        imlink.append(html.Td('',style={'width':'10px'}))
    children.append(html.Table([html.Tr(headers),html.Tr(images),html.Tr(aiac),html.Tr(goesc),html.Tr(peakfl),html.Tr(imlink),html.Tr(html.Td(''))]))#,style={'border-spacing': '50px'}
    imdiv=html.Div(children=children)#[html.P("Flare Info"),html.A("thumbnail image link",href=hek_events.gs_thumburl.iloc[c])])

#    fig = make_subplots(rows=1, cols=nevents,subplot_titles=etitles) #for now...what if there's > 5 events or so?
#
#    # Constants
#    img_width = 250
#    img_height = 250
#    scale_factor = 1#0.5
#
#    # Add invisible scatter trace.
#    # This trace is added to help the autoresize logic work.
#    for c in range(nevents):
#        fig.add_trace(go.Scatter(x=[0, img_width * scale_factor],y=[0, img_height * scale_factor],mode="markers",marker_opacity=0),row=1,col=c+1)
#        fig.update_xaxes(visible=False,range=[0, img_width * scale_factor],row=1,col=c+1)
#        fig.update_yaxes(visible=False,range=[0, img_height * scale_factor],scaleanchor="x",row=1,col=c+1)
#
#        # Add image
#        fig.add_layout_image(
#            dict(
#            x=0,
#            sizex=img_width * scale_factor,
#            y=img_height * scale_factor,
#            sizey=img_height * scale_factor,
#            xref="x",
#            yref="y",
#            opacity=1.0,
#            layer="below",
#            sizing="stretch",
#            source='https://cloud.githubusercontent.com/assets/12302455/16637308/4e476280-43ac-11e6-9fd3-ada2c9506ee1.gif'),row=1,col=c+1)#hek_events.gs_thumburl.iloc[c])) #"https://raw.githubusercontent.com/michaelbabyn/plot_data/master/bridge.jpg"
    ##doesn't work for gifs!
    
    #fig.show(config={'doubleClick': 'reset'}) #add later?
    
    return imdiv#,infotable

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
    bottom_left_coord=rotate_coord(relayoutData[kk[0]],relayoutData[kk[2]],current_observer,current_wcs,output_observer,output_wcs,unit_in='px',binning=binning)
    top_right_coord=rotate_coord(relayoutData[kk[1]],relayoutData[kk[3]],current_observer,current_wcs,output_observer,output_wcs,unit_in='px',binning=binning)
    
    bottom_left_coord.do_rotation()
    top_right_coord.do_rotation()
    
    for c in [bottom_left_coord,top_right_coord]:
        if np.isnan(c.rotated_x_px): #both x and y would be nan, so only need to check one
            try:
                new_rotated_xpx,new_rotated_ypx=zoom_over_empty(bottom_left_coord,top_right_coord,relayoutData,kk)
                setattr(c,'rotated_x_px', new_rotated_xpx)
                setattr(c,'rotated_y_px', new_rotated_ypx)
                #print('rotated coords: ', bottom_left_coord.__dict__,top_right_coord.__dict__) #seems to work
            except IndexError: #don't zoom!
                return None #do nothing
    
    #transform axis ranges to to WCS
    #bottom_left_wcs_noobs=pixel_to_skycoord(relayoutData[kk[0]]*binning,relayoutData[kk[2]]*binning,current_wcs,mode='wcs') #no observer!
    #bottom_left_wcs=SkyCoord(bottom_left_wcs_noobs.Tx,bottom_left_wcs_noobs.Ty,frame='helioprojective',observer=current_observer) #add observer
    #top_right_wcs_noobs=pixel_to_skycoord(relayoutData[kk[1]]*binning,relayoutData[kk[3]]*binning,current_wcs,mode='wcs')
    #top_right_wcs=SkyCoord(top_right_wcs_noobs.Tx,top_right_wcs_noobs.Ty,frame='helioprojective',observer=current_observer) #add observer
    
    #transform from WCS to pixel coords of other subplot
    #testcoord=SkyCoord(0*u.arcsec,0*u.arcsec,frame='helioprojective',observer=output_observer,obstime=output_observer.obstime) ##why is observer= None? that messes things up
    #print(testcoord,bottom_left_wcs.obstime)
    #bottom_left_wcs_out=bottom_left_wcs.transform_to(testcoord.frame)
    #bottom_left_pix=bottom_left_wcs_out.to_pixel(output_wcs)
    #top_right_wcs_out=top_right_wcs.transform_to(testcoord.frame)
    #top_right_pix=top_right_wcs_out.to_pixel(output_wcs)
    #need to divide by 8....
    
    #print(bottom_left_wcs,top_right_wcs)
    #print(bottom_left_wcs_out,top_right_wcs_out)
    #print(pixel_to_skycoord(bottom_left_pix[0],bottom_left_pix[1],output_wcs),pixel_to_skycoord(top_right_pix[0],top_right_pix[1],output_wcs))
    #print('rotated coords: ', bottom_left_coord.__dict__,top_right_coord.__dict__)
    new_layout[outkeys[0]]['range']=[bottom_left_coord.rotated_x_px,top_right_coord.rotated_x_px]
    new_layout[outkeys[1]]['range']=[bottom_left_coord.rotated_y_px,top_right_coord.rotated_y_px]
    #what to do if it's out of the axis range? or if transformation gives NaN in skycoords? use height/width of rectangle instead
    #print(new_layout)
    
    return zaxes, new_layout
    
def zoom_over_empty(c1,c2,relayoutData,kk):
    '''in case of nans in coord rotation, extend the box to match the size of the zoom, given the one non-nan coordinate '''
    zoom_width=relayoutData[kk[1]]-relayoutData[kk[0]]
    zoom_height=relayoutData[kk[3]]-relayoutData[kk[2]]
    
    if np.isnan(c1.rotated_x_px): #this one
        nonnan_x0=c2.rotated_x_px
        nonnan_y0=c2.rotated_y_px
        if np.isnan(nonnan_x0): #if they're both nan!
            return None
        
    else:
        nonnan_x0=c1.rotated_x_px
        nonnan_y0=c1.rotated_y_px
        zoom_width=-1*zoom_width
        zoom_height=-1*zoom_height
        
    return nonnan_x0+zoom_width,nonnan_x0+zoom_height
        
    
def query_hek(time_int,event_type='FL',obs_instrument='AIA',small_df=True,single_result=False):
    time = sn.attrs.Time(time_int[0],time_int[1])
    eventtype=sn.attrs.hek.EventType(event_type)
    #obsinstrument=sn.attrs.hek.OBS.Instrument(obs_instrument)
    res=sn.Fido.search(time,eventtype,sn.attrs.hek.OBS.Instrument==obs_instrument)
    tbl=res['hek']
    names = [name for name in tbl.colnames if len(tbl[name].shape) <= 1]
    df=tbl[names].to_pandas()
    if df.empty:
        return df
    if small_df:
        df=df[['hpc_x','hpc_y','hpc_bbox','frm_identifier','frm_name','fl_goescls','fl_peaktempunit','fl_peakemunit','fl_peakflux','event_peaktime','fl_peakfluxunit','fl_peakem','fl_peaktemp','obs_dataprepurl','gs_imageurl','gs_thumburl']]
        df.drop_duplicates(inplace=True)
    if single_result: #select one
        aa=df.where(df.frm_identifier == 'Feature Finding Team').dropna()
        print(aa.index.values)
        if len(aa.index.values) == 1: #yay
            return aa
        elif len(aa.index.values) > 1:
            return pd.DataFrame(aa.iloc[0]).T
        elif aa.empty: #whoops, just take the first one then
            return pd.DataFrame(df.iloc[0]).T

    return df
    
def rotate_hek_coords(df,observer_in,wcs_in,observer_out,wcs_out,binning=1):
    '''World to pixel and rotate for HEK event coords '''
    xpx,ypx,xrot,yrot,xpxrot,ypxrot=[],[],[],[],[],[] #there's got to be a better way to do this
    lon,lat,lonr,latr=[],[],[],[]
    for i,row in df.iterrows():
        rc=rotate_coord(row.hpc_x,row.hpc_y,observer_in,wcs_in,obs_out=observer_out,wcs_out=wcs_out,binning=binning) #.iloc[0]
        try:
            rc.do_rotation()
            #print(rc.rotated_lon_deg,rc.rotated_lat_deg, rc.rotated_x_arcsec,rc.rotated_y_arcsec)
        except ValueError:
            print("Coordinate (%s,%s) could not be rotated!" % (row.hpc_x,row.hpc_y))
            rc.rotated_x_arcsec=None
            rc.rotated_y_arcsec=None
            rc.rotated_x_px=None
            rc.rotated_y_px=None
        #(pxx,pxy),(xr,yr)=_world_to_pixel(row.hpc_x,row.hpc_y,observer_in,wcs_in,rotate_obs=observer_out,rotate_wcs=wcs_out)
        #do this for each coord in the bounding box too, wow I really hope this isn't slow
        #if rc.rotated_x_arcsec != 0:
        #    print(rc.x_arcsec,rc.y_arcsec,rc.rotated_x_arcsec,rc.rotated_y_arcsec)
        xpx.append(rc.x_px)
        ypx.append(rc.y_px)
        xrot.append(rc.rotated_x_arcsec)
        yrot.append(rc.rotated_y_arcsec)
        xpxrot.append(rc.rotated_x_px)
        ypxrot.append(rc.rotated_y_px)
        lon.append(rc.x_deg)
        lat.append(rc.y_deg)
        lonr.append(rc.rotated_lon_deg)
        latr.append(rc.rotated_lat_deg)
    df['hpc_x_px']=xpx
    df['hpc_y_px']=ypx
    df['hpc_x_rotated']=xrot
    df['hpc_y_rotated']=yrot
    df['x_px_rotated']=xpxrot
    df['y_px_rotated']=ypxrot
    df['hpc_lon']=lon
    df['hpc_lat']=lat
    df['hpc_lon_rotated']=lonr
    df['hpc_lat_rotated']=latr

    return df
