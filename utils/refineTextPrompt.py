prompt = """You are processing the original text parsed from an email newsletter. Your task is to extract and return only the essential content while ensuring that all sentences remain exactly as they are in the original text. Do not alter, rewrite, or summarize any part of the content unless absolutely necessary for clarity.

Remove any extraneous elements that do not contribute to the main content of the newsletter, including:
- Sponsored content, advertisements, and promotional messages  
- Referral links, affiliate links, and subscription prompts  
- Footer messages, disclaimers, and unsubscribe links  
- Any unrelated content, such as "click to subscribe," website banners, or redundant metadata  

Ensure that the final output preserves the original sentence structure, wording, and order, maintaining the integrity of the newsletter’s core content without any unnecessary modifications.

Original Text:  
{parsed_text}
"""
