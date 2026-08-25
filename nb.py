from dataclasses import dataclass
from io import BytesIO
from PIL import Image
import requests


@dataclass(frozen=True)
class GridSize:
    """
    A dataclass representing the layout of page chunks in an image, defined by the number of rows and columns.
    """
    rows: int
    columns: int


class Book:
    BASE = "https://www.nb.no/services/image/resolver"
    MAX_PAGE_CHUNK_SIZE = 2048
    MAX_PAGE_X_RESOLUTION = 1024
    __CHUNKDATA_PLACEHOLDER = "$CHUNKDATA$"
    
    
    # Ctor
    def __init__(self, 
        bookID: str,                                                                    # Book identifier
        pages: int,                                                                     # Number of pages in the book (NOTE: 1-based indexing)
        # // pageEdgeResolutions: list[int],                                                 # ? List of X resolutions for page edge chunks   
        pageSeparator: str = "_",                                                       # ? Separator between bookID and pageNumber
        pageNumberFormat: str = "04d",                                                  # ? Format for page numbers
        pageChunksLayout: GridSize = GridSize(rows=2, columns=2),                       # ? Layout of page chunks in the image
        imageSectionIndex: int = 0,                                                     # ? Assumed to always be 0
        pageFileName: str = "default.jpg",                                              # ? Assumed to always be "default.jpg"
    ) -> None:
        """
        Book
        --
        Class representing a book from the National Library of Norway (Nasjonalbiblioteket). 
        This class provides methods to construct URLs for fetching page 
        images based on the book's identifier and page number.
        
        Args:
            bookID (str): The book identifier, e.g., `"URN:NBN:no-nb_digibok_2009060900016"`
            pages (int): The number of pages in the book, excluding the 4 to 5 cover pages (**NOTE: 1-based indexing**).
            pageSeparator (str): The separator between the bookID and pageNumber in the URL, default is `"_"`
            pageNumberFormat (str): The format for page numbers in the URL, default is `"04d"` (zero-padded to 4 digits)
            pageChunksLayout (GridSize): The layout of page chunks in the image, default is `GridSize(rows=2, columns=2)`
            imageSectionIndex (int): The index of the image section in the URL, default is `0`
            pageFileName (str): The name of the page file in the URL, default is `"default.jpg"`
        """
        # // pageEdgeResolutions (list[int]): A list of X resolutions for a pages edge chunks, e.g., `[232, 236, 240, 244]`. Used in the page chunk URL
                    

        # Attributes
        self._bookID = bookID
        self._pages = pages
        # //self.__pageEdgeResolutions = pageEdgeResolutions
        self._pageSeparator = pageSeparator
        self.__pageNumberFormat = pageNumberFormat
        self.__pageChunksLayout = pageChunksLayout
        self.__imageSectionIndex = imageSectionIndex                                    
        self._pageFileName = pageFileName
      
        
    # Getters
    @property
    def bookID(self) -> str: return self._bookID        
    @property
    def pages(self) -> int: return self._pages


    # Functions
    def page(self, pageNumber: int) -> Image.Image:
        # * Sanity check
        # Ensure the requested page number is within the valid range of pages for the book.
        if pageNumber < 1 or pageNumber > self._pages:
            raise ValueError(f"Page number {pageNumber} is out of range (1-{self._pages})")
        
        # * Generate the page
        # FORMAT: 
        #   "{BASE}/{bookID}{pageSeparator}{pageNumber}/{pageChunk}/{imageResolutionX},/{imageSectionIndex}/{pageFileName}"
        # 
        # EXAMPLES:
        #   https://www.nb.no/services/image/resolver/URN:NBN:no-nb_digibok_2009060900016_0001/0,0,2048,2048/1024,/0/default.jpg
        #   https://www.nb.no/services/image/resolver/URN:NBN:no-nb_digibok_2009060900016_0001/0,2048,2048,1704/1024,/0/default.jpg
        #   https://www.nb.no/services/image/resolver/URN:NBN:no-nb_digibok_2009060900016_0001/2048,0,488,2048/244,/0/default.jpg
        #   https://www.nb.no/services/image/resolver/URN:NBN:no-nb_digibok_2009060900016_0001/2048,2048,488,1704/244,/0/default.jpg
        
        # Generate the page URL pattern
        pageURLPattern = f"{self.BASE}/"                                                                    \
                         f"{self._bookID}{self._pageSeparator}{pageNumber:{self.__pageNumberFormat}}/"      \
                         f"{self.__CHUNKDATA_PLACEHOLDER}/"                                                 \
                         f"{self.__imageSectionIndex}/{self._pageFileName}"

        # Find page chunk URLs
        pageChunkURLs = self.__findPageChunkURLs(pageURLPattern)  
        
        # Fetch page chunks
        pageChunks = self.__fetchPageChunks(pageChunkURLs)
        print(f" INFO: Fetched {len(pageChunks)} page chunks for page {pageNumber}.")
        
        # Combine the fetched page chunks into a single image and return
        return self.__combinePageChunks(pageChunks)
            
    
    def __findPageChunkURLs(self, pageURLPattern: str) -> list[str]:
        # * ALGORITHM:
        # First find all trivial page chunk URLs by looping over a grid with containing 
        # non-X-edge chunks; (self.__pageChunksLayout.rows, self.__pageChunksLayout.columns-1).
        # Then find the page chunk URLs for the x-edge chunks by looping over the last column of the grid
        # with varying X resolutions from self.__pageEdgeResolutions to generate and test candidate URLs.
        
        # NOTE: 
        # ! FOR SOME REASON WHILE PROTOTYPING DID THE Nasjonalbilioteket API RETURN "403 FORBIDDEN" 
        # ! WHEN TRYING TO FETCH CHUNK DATA WITH OVERFLOWING X_RESOLUTION DATA! E.g. `$CHUNKDATA$ = "x,y,w,h/1024,"`
        # ! WHILE THE LAST CHUNK IN THE GRID REALLY WAS AN X-EDGE CHUNK WITH `$CHUNKDATA$ = "x,y,w,h/244,"`.
        # ! THIS ISN'T THE CASE WHEN FETCHING RIGHT NOW, AS IT RETURNS THE CORRECT IMAGES, EVEN WITH OVERFLOWING
        # ! X_RESOLUTION DATA. THIS IS WHY THE FOLLOWING CODE ISN'T FOLLOWING THE ALGORITHM DESCRIBED ABOVE!
        # ! THIS IS ALSO WHY THE `pageEdgeResolutions` ARGUMENT IS COMMENTED OUT IN THE CONSTRUCTOR, AS IT'S UNUSED!
        
        # Initialize an empty list to store the generated page chunk URLs
        pageChunkURLs = []
        
        # Loop over the grid layout to generate page chunk URLs for each chunk in the grid
        for row in range(self.__pageChunksLayout.rows):
            for col in range(self.__pageChunksLayout.columns):
                # Calculate the X and Y coordinates for the current chunk
                x = col * self.MAX_PAGE_CHUNK_SIZE
                y = row * self.MAX_PAGE_CHUNK_SIZE
                
                # Construct the page chunk URL by replacing the placeholder with the calculated coordinates
                pageChunkURL = pageURLPattern.replace(
                    self.__CHUNKDATA_PLACEHOLDER, 
                    f"{x},{y},{self.MAX_PAGE_CHUNK_SIZE},{self.MAX_PAGE_CHUNK_SIZE}/{self.MAX_PAGE_X_RESOLUTION},"
                )
                
                # Store the constructed page chunk URL in the list
                pageChunkURLs.append(pageChunkURL)
        
        # Return the list of generated page chunk URLs
        return pageChunkURLs
    
    
    def __fetchPageChunks(self, pageChunkURLs: list[str]) -> list[bytes]:
        # Fetch the page chunks from the generated URLs and return them as a list of images.
        pageChunks = []
        
        for url in pageChunkURLs:
            # Fetch the image content from the URL using an HTTP GET request
            response = requests.get(url)
            
            # Store the image content
            if response.status_code == 200:     pageChunks.append(response.content)
            else:                               print(f"ERROR: Failed to fetch \"{url}\" (Status code {response.status_code})")
        
        # Return the list of fetched page chunks
        return pageChunks
    
    
    def __combinePageChunks(self, pageChunks: list[bytes]) -> Image.Image:
        # * Sanity check
        # Ensure the number of fetched page chunks matches the expected layout
        if len(pageChunks) != (self.__pageChunksLayout.rows * self.__pageChunksLayout.columns):
            raise ValueError(
                f"Expected {self.__pageChunksLayout.rows * self.__pageChunksLayout.columns} chunks, got {len(pageChunks)}"
            )
        
        # * Combine
        # Temporary variables for clarity
        rows, columns = self.__pageChunksLayout.rows, self.__pageChunksLayout.columns
        
        # Load images fully while their in-memory byte streams are available.
        images = []

        for imageData in pageChunks:
            with BytesIO(imageData) as stream:
                image = Image.open(stream).convert("RGB")
                images.append(image.copy())
        
        # Find the largest chunk width in each column and height in each row.
        columnWidths = [
            max(images[row * columns + column].width for row in range(rows))
            for column in range(columns)
        ]

        rowHeights = [
            max(images[row * columns + column].height for column in range(columns))
            for row in range(rows)
        ]

        width  = sum(columnWidths)
        height = sum(rowHeights)

        combined = Image.new("RGB", (width, height))

        # Paste each chunk at the correct grid position.
        y = 0

        for row in range(rows):
            x = 0

            for column in range(columns):
                image = images[row * columns + column]
                combined.paste(image, (x, y))
                
                x += columnWidths[column]
            y += rowHeights[row]

        # Return the combined image
        return combined 