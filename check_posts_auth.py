#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

load_dotenv()

wp_url = os.getenv('WP_URL')
wp_user = os.getenv('WP_USER')
wp_pass = os.getenv('WP_APP_PASSWORD')

for post_id in [7237, 7239, 7240, 7243]:
    print(f'=== Post {post_id} ===')
    try:
        r = requests.get(f'{wp_url}/wp-json/wp/v2/posts/{post_id}',
                         auth=(wp_user, wp_pass), timeout=10)
        if r.status_code == 200:
            p = r.json()
            print(f"Status: {p['status']}")
            print(f"Title: {p['title']['rendered'][:80]}")
            print(f"Featured Media: {p.get('featured_media', 0)}")
            content = p['content']['rendered']
            print(f"Content Length: {len(content)}")

            # Check for various forms of ```html marker
            markers = ['```html', '&#96;&#96;&#96;html', '`html']
            found = False
            for marker in markers:
                if marker in content:
                    print(f'⚠️ FOUND marker: {marker}')
                    idx = content.find(marker)
                    print(f"Context: ...{content[max(0,idx-50):idx+150]}...")
                    found = True
                    break

            if not found:
                print('✓ No html markers found')
                print(f"First 300 chars: {content[:300]}")
        else:
            print(f'Status Code: {r.status_code}')
            if r.status_code == 404:
                print('Post not found (may be deleted)')
    except Exception as e:
        print(f'Error: {e}')
    print()
