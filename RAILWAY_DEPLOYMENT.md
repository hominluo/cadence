# Deploying to Railway

This guide will help you deploy this application to Railway.com.

## Prerequisites
- A GitHub account with this repository pushed to it
- A Railway.com account
- OpenAI API key
- Google Drive credentials file (`credentials.json`)

## Deployment Steps

1. Sign up for Railway at https://railway.com/ if you haven't already.

2. From the Railway dashboard, click **New Project**.

3. Select **Deploy from GitHub repo**.

4. Connect your GitHub account if not already connected, and select this repository.

5. Railway will automatically detect your Python application and start the deployment process.

6. Add the following environment variables in the Railway dashboard (Settings > Variables):
   - `OPENAI_API_KEY`: Your OpenAI API key

7. For the Google Drive credentials:
   - Go to the "Files" tab in your Railway project
   - Upload your `credentials.json` file

8. Railway will automatically build and deploy your application.

9. Once deployment is complete, you can access your app via the URL provided by Railway. The default endpoint will be available at `/v2/answer` for querying.

## Testing the Deployment

You can test the deployment with cURL:

```bash
curl -X 'POST' \
  'https://your-railway-app-url/v2/answer' \
  -H 'accept: */*' \
  -H 'Content-Type: application/json' \
  -d '{
  "prompt": "What is my Linkedin?"
}'
```

## Troubleshooting

- If the build fails, check the Railway logs for specific error messages.
- Ensure your `credentials.json` file is properly uploaded and contains valid Google Drive credentials.
- Verify that all required environment variables are correctly set.
- If you make changes to your app, push them to GitHub, and Railway will automatically rebuild and redeploy your application. 