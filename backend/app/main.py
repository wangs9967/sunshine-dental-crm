from fastapi import FastAPI
app=FastAPI(title='阳光口腔会员运营管理系统 API',version='0.1.0')
@app.get('/health')
def health(): return {'status':'ok'}
