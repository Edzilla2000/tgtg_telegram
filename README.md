
# Too Good To Go to Telegram notification

This project will alert you using Telegram when one of your favorited Too Good To Go bag is available.




## Deployment

To run this project, you need to rename the env_example file to .env, and edit it with the required parameters.

You can then run the script on a schedule. You will only be alerted once every 2 hours per bag.

To obtain your Too Good To Go credentials, you can use the following snippet:
```python
from tgtg import TgtgClient

client = TgtgClient(email="<your_email>")
credentials = client.get_credentials()
print(credentials)
```


## Environment Variables

To run this project, you will need to add the following environment variables to your .env file

`TGTG_ACCESS_TOKEN`: Your Too Good to Go access_token

`TGTG_REFRESH_TOKEN`: Your Too Good to Go refresh_token

`TGTG_USER_ID`: Your Too Good to Go user_id

`TGTG_COOKIE`: Your Too Good to Go cookie

`TELEGRAM_CHAT_ID`: The chat_id you want to notify in Telegram

`TELEGRAM_API_KEY`: Your Telegram bot API key



