5/3/2025 13:05 CDT version -- Ted Shaowang

Install
```bash
python3.11 -m venv env
source env/bin/activate
pip3 install -r requirements.txt -U
```

Make sure you have Google Drive `credentials.json` in the same folder, and OPENAI_API_KEY in your environmental variable.
```bash
python3 app.py
curl -X 'POST'   'http://0.0.0.0:8000/v2/answer'   -H 'accept: */*'   -H 'Content-Type: application/json'   -d '{
  "prompt": "Who is the main character?"
}'
```
