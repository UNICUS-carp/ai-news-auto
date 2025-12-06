#!/usr/bin/env python3
import requests
import json

post_ids = [7237, 7239, 7240, 7243]
for post_id in post_ids:
    print(f'=== Post ID {post_id} ===')
    try:
        url = f'https://unicus.top/wp-json/wp/v2/posts/{post_id}'
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            p = r.json()
            print(f"Date: {p['date']}")
            print(f"Status: {p['status']}")
            print(f"Title: {p['title']['rendered'][:80]}")
            print(f"Featured Media: {p.get('featured_media', 0)}")
            content = p['content']['rendered']
            print(f"Content Length: {len(content)}")

            # Check for ```html marker
            if '```html' in content:
                print('⚠️ FOUND ```html in content!')
                idx = content.find('```html')
                print(f"Context: {content[max(0,idx-50):idx+150]}")
            else:
                print('✓ No ```html marker found')

            print(f"First 300 chars: {content[:300]}")
        else:
            print(f"Error: HTTP Status {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    print()
