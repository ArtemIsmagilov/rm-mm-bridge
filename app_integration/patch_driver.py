import glob
path_to_mattermost = glob.glob('/usr/local/lib/python3.11/site-packages/mattermostdriver/websocket.py', recursive=True)
p = path_to_mattermost.pop()
print(p, flush=True)

with open(p, mode='r+', encoding='utf-8') as websocket_file:
    old_text = websocket_file.read()
    new_text = old_text.replace('CLIENT_AUTH', 'SERVER_AUTH', 1)
    websocket_file.truncate(0)
    websocket_file.seek(0)
    websocket_file.write(new_text)


