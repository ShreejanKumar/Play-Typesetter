import os
import streamlit as st
from openai import OpenAI
import json
import nest_asyncio
import asyncio
from playwright.async_api import async_playwright
import PyPDF2
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

def get_response(chapter, font_size, lineheight):
  
  # Set up OpenAI API client
    
  api_key = st.secrets["Openai_api"]
  client = OpenAI(
        # This is the default and can be omitted
        api_key = api_key
    )
  
  # Set up OpenAI model and prompt
  model="gpt-4o-mini-2024-07-18"
  prompt_template = """
You are an expert book formatter.  
This is a book chapter, which may include sections of a play. Your job is to output a typeset file (USING HTML) which can be converted to a PDF book. Ensure the content is beautifully formatted, adhering to all rules of book formatting, and easily readable in a web browser. Include these features in HTML and pay special attention to point 7:

1. Paragraph Formatting 
   - Indentation: Use a small indent (about 1 em) for the first line of each paragraph, or opt for larger spacing between paragraphs if not using indentation.

2. Line Length 
   - Optimal Line Length: Aim for 50-75 characters per line (including spaces). Ensure a comfortable reading experience.

3. Line Spacing (Leading) 
   -*Comfortable Reading: Set line spacing (leading) to around 120-145% of the font size.

4. Margins 
   - Top and bottom margins for paragraphs should be 0.1em and 0.2em, respectively.  
   - Left and right margins should be minimal to emulate a book-like layout.

5. Consistency 
   - Ensure uniform styles for similar elements (e.g., headings, captions, block quotes) throughout.

6. Special Formatting  
   - Format special segments (e.g., poetry, quotes, or exclamatory expressions) appropriately using italics.  

7. Plays 
   - For plays, follow these conventions:  
     a. Character names should be in uppercase and bold, left-aligned.  
     b. Dialogue should be on the next line after the character name, indented by 2 em.  
     c. Stage directions or actions should always be in italics, enclosed in parentheses, and indented similarly.
     d. The chapter names can be in the form of Acts. Format them as we format chapter titles.

8. Styling  
   - Use various HTML tags (e.g., headings, bold, italics) as needed, but do not use colors for text.  

9. Multilingual Words  
   - Single words in other languages (e.g., Hindi or Spanish) should be italicized.  

10. Chapter Heading  
   - The chapter heading should be centrally aligned and start at the one-fourth level of a new page, with extra margin on the top.  
   - Leave additional space between the chapter heading and the first paragraph.

11. General Formatting  
   - Avoid using inline styles wherever possible; rely on semantic tags.  
   - Do not include anything else like ```html in the response. Start directly with the `<!DOCTYPE html>` line.

12. Font size and line height
   - Use fontsize as <<fontsize>>
   - Use line height as <<lineheight>>
   
Here is the target chapter: <<CHAPTER_TEXT>>
"""
  prompt = prompt_template.replace("<<CHAPTER_TEXT>>", chapter).replace("<<fontsize>>", font_size + "px").replace("<<lineheight>>", lineheight)
  chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=model,
	temperature = 0
    )

  response = chat_completion.choices[0].message.content
  return response

def save_response(response):
    html_pth = 'neww.html'
    with open(html_pth, 'w', encoding='utf-8') as file:
        file.write(response)
    return html_pth


nest_asyncio.apply()

async def html_to_pdf_with_margins(html_file, output_pdf):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        with open(html_file, 'r', encoding='utf-8') as file:
            html_content = file.read()

        await page.set_content(html_content, wait_until='networkidle')

        pdf_options = {
            'path': output_pdf,
            'format': 'A4',
            'margin': {
                'top': '70px',
                'bottom': '60px',
                'left': '70px',
                'right': '40px'
            },
            'print_background': True
        }

        await page.pdf(**pdf_options)
        await browser.close()

def get_pdf_page_count(pdf_file):
    with open(pdf_file, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        return len(reader.pages)
    
def create_overlay_pdf(overlay_pdf, total_pages, starting_page_number, book_name, author_name, font, first_page_position="right"):
    c = canvas.Canvas(overlay_pdf, pagesize=A4)
    width, height = A4

    def draw_header_footer(page_number, is_right_side):
        # Set font for headers and footers
        c.setFont(font, 12)

        if page_number == starting_page_number:
            # First page of the chapter: Draw page number at the bottom aligned with text
            footer_y = 30  # Adjust this value to match the bottom text's baseline
            c.drawCentredString(width / 2, footer_y, f'{page_number}')

        elif is_right_side:
            # Right-side pages (odd): Draw header on the right
            header_text = book_name
            c.drawCentredString(width / 2, height - 40, header_text)
            # Draw page number at the right header with some gap from the edge
            c.drawString(width - 84, height - 40, f'{page_number}')  # Adjusted x-coordinate for gap

        else:
            # Left-side pages (even): Draw header on the left
            header_text = author_name
            c.drawCentredString(width / 2, height - 40, header_text)
            # Draw page number at the left header with some gap from the edge
            c.drawString(62, height - 40, f'{page_number}')  # Adjusted x-coordinate for gap

    # Create pages for the overlay
    for i in range(total_pages):
        current_page_number = starting_page_number + i  # Continuous page numbering
        is_right_side = ((current_page_number - starting_page_number) % 2 == 0) if first_page_position == "right" else ((current_page_number - starting_page_number) % 2 != 0)
        draw_header_footer(current_page_number, is_right_side)
        c.showPage()

    c.save()

def overlay_headers_footers(main_pdf, overlay_pdf, output_pdf):
    pdf_writer = PdfWriter()

    # Load the main PDF and the overlay PDF
    with open(main_pdf, 'rb') as main_file, open(overlay_pdf, 'rb') as overlay_file:
        main_pdf_reader = PdfReader(main_file)
        overlay_pdf_reader = PdfReader(overlay_file)

        # Ensure the overlay PDF has the same number of pages as the main PDF
        print(len(overlay_pdf_reader.pages))
        print(len(main_pdf_reader.pages))
        if len(overlay_pdf_reader.pages) != len(main_pdf_reader.pages):
            raise ValueError("The number of pages in the overlay PDF does not match the number of pages in the main PDF.")

        # Overlay headers and footers on each page
        for page_num in range(len(main_pdf_reader.pages)):
            main_page = main_pdf_reader.pages[page_num]
            overlay_page = overlay_pdf_reader.pages[page_num]

            # Merge the overlay onto the main page
            main_page.merge_page(overlay_page)

            pdf_writer.add_page(main_page)

    # Write the combined PDF to the output file
    with open(output_pdf, 'wb') as outfile:
        pdf_writer.write(outfile)