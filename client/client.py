from starlette.responses import FileResponse 
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI

# Mockup nationbuilder server
tvquiz_client = FastAPI()

'''
Client-side single page app
'''

@tvquiz_client.get("/")
async def open_root_html():
    return FileResponse('client/index.html')

tvquiz_client.mount("/src", StaticFiles(directory="client/src"), name="src")
tvquiz_client.mount("/data", StaticFiles(directory="client/data"), name="data")
