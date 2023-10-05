from starlette.responses import FileResponse 
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI

# Mockup nationbuilder server
pd_client = FastAPI()

'''
Client-side single page app
'''

@pd_client.get("/")
async def open_root_html():
    return FileResponse('client/index.html')

pd_client.mount("/src", StaticFiles(directory="client/src"), name="src")
pd_client.mount("/data", StaticFiles(directory="client/data"), name="data")
