import time
import asyncio
import re
import requests
from telethon.sync import TelegramClient
from telethon import errors

class TelegramForwarder:
    def __init__(self, api_id, api_hash, phone_number):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = TelegramClient('session_' + phone_number, api_id, api_hash)

    async def list_chats(self):
        await self.client.connect()

        # Ensure you're authorized
        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone_number)
            try:
                await self.client.sign_in(self.phone_number, input('Enter the code: '))
            except errors.rpcerrorlist.SessionPasswordNeededError:
                password = input('Two-step verification is enabled. Enter your password: ')
                await self.client.sign_in(password=password)

        # Get a list of all the dialogs (chats)
        dialogs = await self.client.get_dialogs()
        chats_file = open(f"chats_of_{self.phone_number}.txt", "w", encoding="utf-8")
        # Print information about each chat
        for dialog in dialogs:
            print(f"Chat ID: {dialog.id}, Title: {dialog.title}")
            chats_file.write(f"Chat ID: {dialog.id}, Title: {dialog.title} \n")

        print("List of groups printed successfully!")

    # Function to expand a shortened URL
    def expand_url(self, short_url):
        try:
            response = requests.head(short_url, allow_redirects=True, timeout=10)
            return response.url  # Returns the final expanded URL
        except Exception as e:
            print(f"Error expanding URL: {e}")
            return None

    # Function to shorten a URL using TinyURL API
    def shorten_url(self, long_url):
        try:
            response = requests.get(f"http://tinyurl.com/api-create.php?url={long_url}", timeout=10)
            return response.text  # Returns the shortened URL
        except Exception as e:
            print(f"Error shortening URL: {e}")
            return None

    # Function to modify the link by adding or replacing an affiliate code
    def modify_link(self, link, affiliate_code="91304036201-21"):
        # Check if the URL already contains a 'tag' parameter
        if "tag=" in link:
            # Replace the existing tag with your affiliate code
            link = re.sub(r'tag=[^&]+', f'tag={affiliate_code}', link)
        else:
            # Append your affiliate code if no 'tag' parameter exists
            if "?" in link:
                link = f"{link}&tag={affiliate_code}"
            else:
                link = f"{link}?tag={affiliate_code}"
        return link

    # Function to process and modify message text (only for https://amzn.to/... links)
    def process_message_text(self, text):
        # Regular expression to detect URLs starting with https://amzn.to/
        url_pattern = r'(https://amzn\.to/\S+)'
        urls = re.findall(url_pattern, text)

        for original_url in urls:
            # Step 1: Expand the shortened URL
            expanded_url = self.expand_url(original_url)
            if not expanded_url:
                continue  # Skip if expansion fails

            # Step 2: Modify the expanded URL with affiliate code
            modified_url = self.modify_link(expanded_url)

            # Step 3: Re-shorten the modified URL (optional)
            re_shortened_url = self.shorten_url(modified_url)
            if not re_shortened_url:
                re_shortened_url = modified_url  # Use the modified URL if re-shortening fails

            # Replace the original URL with the re-shortened URL
            text = text.replace(original_url, re_shortened_url)

        return text

    async def forward_messages_to_channel(self, source_chat_id, destination_channel_id, keywords):
        await self.client.connect()

        # Ensure you're authorized
        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone_number)
            await self.client.sign_in(self.phone_number, input('Enter the code: '))

        last_message_id = (await self.client.get_messages(source_chat_id, limit=1))[0].id

        while True:
            print("Checking for messages and forwarding them...")
            # Get new messages since the last checked message
            messages = await self.client.get_messages(source_chat_id, min_id=last_message_id, limit=None)

            for message in reversed(messages):
                # Check if the message contains any Amazon links
                if message.text:
                    # Regular expression to detect Amazon links
                    amazon_link_pattern = r'https://amzn\.to/\S+'
                    if not re.search(amazon_link_pattern, message.text):
                        print("No Amazon link found. Skipping message.")
                        continue  # Skip messages without Amazon links

                # Process the message text to modify links
                processed_text = self.process_message_text(message.text)

                # Forward the processed message to the destination channel
                await self.client.send_message(destination_channel_id, processed_text)

                print("Message forwarded")

                # Update the last message ID
                last_message_id = max(last_message_id, message.id)

            # Add a delay before checking for new messages again
            await asyncio.sleep(5)  # Adjust the delay time as needed


# Function to read credentials from file
def read_credentials():
    try:
        with open("credentials.txt", "r") as file:
            lines = file.readlines()
            api_id = lines[0].strip()
            api_hash = lines[1].strip()
            phone_number = lines[2].strip()
            return api_id, api_hash, phone_number
    except FileNotFoundError:
        print("Credentials file not found.")
        return None, None, None

# Function to write credentials to file
def write_credentials(api_id, api_hash, phone_number):
    with open("credentials.txt", "w") as file:
        file.write(api_id + "\n")
        file.write(api_hash + "\n")
        file.write(phone_number + "\n")

async def main():
    # Attempt to read credentials from file
    api_id, api_hash, phone_number = read_credentials()

    # If credentials not found in file, prompt the user to input them
    if api_id is None or api_hash is None or phone_number is None:
        api_id = input("Enter your API ID: ")
        api_hash = input("Enter your API Hash: ")
        phone_number = input("Enter your phone number: ")
        # Write credentials to file for future use
        write_credentials(api_id, api_hash, phone_number)

    forwarder = TelegramForwarder(api_id, api_hash, phone_number)
    
    print("Choose an option:")
    print("1. List Chats")
    print("2. Forward Messages")
    
    choice = input("Enter your choice: ")
    
    if choice == "1":
        await forwarder.list_chats()
    elif choice == "2":
        source_chat_id = int(input("Enter the source chat ID: "))
        destination_channel_id = int(input("Enter the destination chat ID: "))
        print("Enter keywords if you want to forward messages with specific keywords, or leave blank to forward every message!")
        keywords = input("Put keywords (comma separated if multiple, or leave blank): ").split(",")
        
        await forwarder.forward_messages_to_channel(source_chat_id, destination_channel_id, keywords)
    else:
        print("Invalid choice")

# Start the event loop and run the main function
if __name__ == "__main__":
    asyncio.run(main())