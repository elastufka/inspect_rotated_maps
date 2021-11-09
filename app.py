import dash
import dash_core_components as dcc
import dash_html_components as html
#import dash_table
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
#import dash_design_kit as ddk
#import dash_daq as daq

import plotly.graph_objects as go
#import plotly.io as pio
import plotly.colors
import plotly.express as px

from plotly.subplots import make_subplots

import pandas as pd
import numpy as np
import glob

from datetime import datetime as dt
from rotate_maps_utils import *

#from collections import Counter
#import base64

external_stylesheets = [dbc.themes.SOLAR] #lol
app = dash.Dash(__name__,external_stylesheets=external_stylesheets) #__name__,
#server = app.server #for Heroku
colorscales = ['blackbody','blues','reds','jet','reds_r','sdoaia171','sdoaia211','sdoaia1600']#px.colors.named_colorscales()

#image_filename = '/Users/wheatley/Documents/Solar/DEM/banner.png' # replace with your own image
#encoded_image = base64.b64encode(open(image_filename, 'rb').read())

#tt=pio.templates['plotly']
#tt.layout.paper_bgcolor="#839496"

imstyle={'height':500} #starting height of image element

image_df=pd.read_json('data/image_df.json') #save time on loading
hdf=pd.read_json('data/hdf.json')
#load_data()#load_example_data()
tsorted=image_df.index.sort_values()
#initial images
rows,fig=image_grid(image_df,hdf,'2021-05-09T04:34:47','linear',0,300,cscale='Blues')
rows,fig2=image_grid_PIL(image_df,hdf,'2021-05-09T04:34:47','linear',0,300,cscale='Blues')
imdiv=hek_images(hdf,'2021-05-09T04:34:47')
style0={'height':rows*300,'min-height':'550px'}

########### layout

app.layout = html.Div([html.Div(children=dbc.Jumbotron([html.H1("Rotated AIA maps", className="display-3"),
#   html.P(
#       "Choose your poison ",
#       className="lead",
#   ),
   #html.Hr(className="my-2"),
#   html.Div([
#        html.Div(html.P(children=[
#        "by ", html.A("Erica Lastufka",href="https://github.com/elastufka/")]),style={'width':'70%','display': 'inline-block','verticalAlign':'middle'}),
#    ])
    ],style={'background-image': 'url(/assets/so.png)','background-size':'50% 100%','min-height':'150px','background-repeat':'no-repeat','background-position':'right'})),
    dcc.Tabs([
    dcc.Tab(label='Inspect Results',children=[
    html.Div(
           dcc.Dropdown(
                id='target',
                options=[{'label': str(i), 'value': i} for i in tsorted],value='2021-05-09T04:34:47'),style={'width': '35%', 'display': 'inline-block','verticalAlign':'top'}), #later make multi=True
  html.Div(
         dcc.Dropdown(
              id='colorscale',
              options=[{"value": x, "label": x} for x in colorscales],value='reds'),style={'width': '25%', 'display': 'inline-block','verticalAlign':'top'}),

    html.Div(dbc.RadioItems(id='scale',options=[{'label': i, 'value': i} for i in ['log','linear']],value='linear',inline=True),
                              style={'width': '15%', 'display': 'inline-block','verticalAlign':'top'}),
    html.Div(html.P('DN/s range  ',style={'text-align':'center'}),style={'width': '12%', 'display': 'inline-block','verticalAlign':'top'}),
              html.Div([
                  dcc.Input(id='vmin',type='text',value="0",debounce=True,style={'width': 50}),
                  dcc.Input(id='vmax',type='text',value="300",debounce=True,style={'width': 50})],
                              style={'width': '10%', 'display': 'inline-block','verticalAlign':'top'}),
 html.Div(dcc.Graph(id='display-images',figure=fig,style=style0)),
 html.Div(dcc.Graph(id='display-images2',figure=fig2,style=style0)),
 html.H2(children=dbc.Alert('HEK Events',color='secondary')),
 html.Div(id='hek-info',children=imdiv),
 #html.Div(id='infotable',children=infotable),
    html.Div(children=["Copyright 2021 ",html.A("Erica Lastufka",href="https://github.com/elastufka/")]),]),
    dcc.Tab(label='Download and Rotate',children=[
        html.Div("Nothing here yet!",style={'padding': '1em'})])
    ]),
    ])


#@app.callback(
#    [Output('display-images', 'figure'),Output('display-images', 'style')],
#    [Input('target','value'),Input('scale', 'value'), Input('vmin','value'),Input('vmax','value')])
#
#def update_image_fig(target,scale,vmin,vmax):
#    #if timeit:
#    #    start_time=dt.now()
#    rows,fig=image_grid(image_df,target,scale,vmin,vmax)
#
#    style={'height':rows*300,'min-height':'500px'} #px, see if this works
#    #if timeit:
#    #    print("Image callback took: ",(dt.now()-start_time).total_seconds())
#    #print(style)
#    #print(fig,style)
#    return fig, style


@app.callback(
[Output('display-images', 'figure'),Output('display-images2','figure')],
    [Input('target', 'value'),Input('scale', 'value'), Input('vmin','value'),Input('vmax','value'),Input("colorscale", "value"),Input('display-images', 'relayoutData')],State('display-images','figure'))
    
def update_image_fig(target,scale,vmin,vmax,cscale,relayoutData,fig): #hopefully only when display characteristics
    tnow=dt.now()
    rescale_data=False
    try:
        aa=fig['data'][0]['current_colorscale']
    except KeyError: #first time State has been input/calculated?
        fig['data'][0]['current_colorscale']='reds'
        fig['data'][0]['datascale']='linear'

    #currently assumes target is a single value, not multiple
    tnames=[fig['data'][i]['name'] for i in range(len(fig['data'])) if i%2 == 0]
    tnames.sort()
    if type(target)==str:
        target=[target]
    target.sort()
    #print(tnames,target)
    if target[0] not in tnames: #current name of data ... need to update the whole figure
        print("generating new figure",tnames,target)
        rows,fig=image_grid(image_df,hdf,target,scale,vmin,vmax,cscale=cscale)
        _,fig2=image_grid_PIL(image_df,hdf,target[0],scale,vmin,vmax,cscale=cscale)
        return fig,fig2
        
    if cscale !=fig['data'][0]['current_colorscale']:
        #if not the same colorscale...
        try:
            colorsc=getattr(px.colors.sequential,cscale.capitalize())
        except AttributeError:
            colorsc=mplcmap_to_plotly(cscale)
        ccolors, scal = plotly.colors.convert_colors_to_same_type(colorsc)
        cont_colorscale = plotly.colors.make_colorscale(ccolors, scale=scal)
        fig['data'][0]['current_colorscale']=cscale

    #print(scale, fig['data'][i]['z'])
    if scale != fig['data'][0]['datascale']: #current scale - actually this isn't in here anywhere.
        fig['data'][0]['datascale']=scale
        rescale_data=True
        if scale == 'log':
            #print(type(image_df.binned_data_original.loc[target[0]][0]),np.array(image_df.binned_data_original.loc[target[0]][0]).shape)
            oarr=np.array(image_df.binned_data_original[target[0]][0]).astype(float)
            rarr=np.array(image_df.binned_data_rotated[target[0]][0]).astype(float)
            ononzero=np.isfinite(oarr)
            rnonzero=np.isfinite(rarr)
            oarr[np.where(ononzero==False)]==0.0
            rarr[np.where(rnonzero==False)]==0.0

            fig['data'][0]['z']=np.log10(oarr.astype(float)) #take the original data....okay I see how this could be tricky.
            fig['data'][1]['z']=np.log10(rarr.astype(float))
        else:
            fig['data'][0]['z']=image_df.binned_data_original[target[0]] #assume 1 target
            fig['data'][1]['z']=image_df.binned_data_rotated[target[0]] #assume 1 target

    if scale == 'log':
        if not np.isinf(np.log10(float(vmin))):
            vmin_scaled=np.log10(float(vmin))
        else:
            vmin_scaled=0
        vmax_scaled=np.log10(float(vmax))
    else:
        vmin_scaled=vmin
        vmax_scaled=vmax

    for i in range(len(fig['data'])):
        fig['data'][i]['zmin']=vmin_scaled #str?
        fig['data'][i]['zmax']=vmax_scaled
        try:
            fig['data'][i]['colorscale']=cont_colorscale
        except UnboundLocalError:
            pass

    #is it zoomed on one? zoom on the other using the coordinate transform
    try:
        kk=list(relayoutData.keys())
        if 'autosize' not in kk and 'xaxis.showspikes' not in kk: #it's been zoomed
            #which plot is zoomed? axis vs axis2
            try:
                to_zoom,new_layout=transform_zoom(relayoutData,image_df.wcs_original[target[0]],image_df.wcs_rotated[target[0]],image_df.observer_original[target[0]],image_df.observer_rotated[target[0]],binning=image_df.binning_original[target[0]])
                for ax in to_zoom:
                    fig['layout'][ax]['range']=new_layout[ax]['range']
            except IndexError: #None, do nothing
               pass
            #print(new_layout)

    except AttributeError:
        pass

    #_,fig2=image_grid_PIL(image_df,hdf,target[0],scale,vmin,vmax,cscale=cscale)
    
    print('Time to execute callback: ',dt.now()-tnow)
    return fig,fig#2
    
@app.callback(
Output('hek-info', 'children'),
    Input('target', 'value'))

def update_thumbnails_and_info(t):
    imdiv=hek_images(hdf,t)
    return imdiv


if __name__ == '__main__':
    app.run_server(debug=True)
