from pathlib import Path
from nb import Book
import img2pdf
import os


# Create a Book instance with the specified bookID and number of pages
ALGORITMER_OG_DATASTRUKTURER = Book(bookID="URN:NBN:no-nb_digibok_2009060900016", pages=309 -5)

# Create a directory to store the downloaded page files
pageDirectory = Path("temp")
os.makedirs(pageDirectory, exist_ok=True)

# List to store the paths of the downloaded page files
pageFiles = []

try:
    for pageNumber in range(1, ALGORITMER_OG_DATASTRUKTURER.pages + 1):
        # Load the page image using the Book instance
        image = ALGORITMER_OG_DATASTRUKTURER.page(pageNumber)

        # Create a temporary file path for the page image
        pagePath = pageDirectory / f"page-{pageNumber:04d}.png"
        image.save(pagePath, format="PNG")
        pageFiles.append(pagePath)

        # Logging
        print(f" INFO: Saved page {pageNumber}/{ALGORITMER_OG_DATASTRUKTURER.pages}")

    # Convert the downloaded page images to a single PDF file
    with open("Algoritmer og Datastrukturer.pdf", "wb") as pdf:
        pdf.write(img2pdf.convert([str(file) for file in pageFiles]))

finally:
    # Clean up the temporary page files
    for pagePath in pageFiles:
        pagePath.unlink(missing_ok=True)
