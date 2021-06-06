# OnShape-CAD-Parser

A simple parser to collect CAD construction data from OnShape. It's built on [Onshape-public/apikey](https://github.com/onshape-public/apikey). Python 2 (2.7.9+) is required.

---

### Usage
- Clone this repo
    ```sh
    $ git clone https://github.com/onshape-public/apikey.git
    $ cd onshape-public-apikey
    $ git submodule init
    $ git submodule update
    ```
- Install dependencies
    ```sh
    $ pip install -r requirements.txt
    ```

- Create a `creds.json` file in the root project folder, with your Onshape developer keys: [instruction here](https://github.com/onshape-public/apikey/tree/master/python#running-the-app).

- Run the python script
    ```sh    
    # some test examples
    $ python process.py --test
    # run on links provied by ABC dataset
    $ python process.py
    ```
    Results are saved as JSON files following the style of [Fusion360 Gallery dataset](https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/docs/reconstruction.md).
