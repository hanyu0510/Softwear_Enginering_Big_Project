import uvicorn

if __name__ == "__main__":
    # factory模式避免导入时提前创建第二套应用/数据库。
    uvicorn.run("app.main:create_app",factory=True,host="127.0.0.1",port=8002)
