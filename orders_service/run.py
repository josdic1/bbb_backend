# orders_service/run.py
import uvicorn

if __name__ == "__main__":
    # This points to the 'app' variable inside the 'main.py' file inside the 'app' folder
    uvicorn.run("app.main:app", host="127.0.0.1", port=8083, reload=True)