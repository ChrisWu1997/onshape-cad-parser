# OnShape-CAD-Parser

A simple parser to collect CAD construction data from OnShape. It's part of our project [DeepCAD: A Deep Generative Network for Computer-Aided Design Models]().

It's built on [Onshape-public/apikey](https://github.com/onshape-public/apikey). Python 2 (2.7.9+) is required.

---

### Dependencies
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

- Follow [this instruction](https://github.com/onshape-public/apikey/tree/master/python#running-the-app) to create a `creds.json` file in the root project folder, filled with your Onshape developer keys:
    ```json
    {
        "https://cad.onshape.com": {
            "access_key": "ACCESS KEY",
            "secret_key": "SECRET KEY"
        }
    }
    ```

### Usage
- Run on some test examples:
    ```sh
    $ python process.py --test # some test examples
    ```
    Results are saved as JSON files following the style of [Fusion360 Gallery dataset](https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/docs/reconstruction.md).

- ABC dataset provides a large collection of Onshape CAD designs with web links [here](https://archive.nyu.edu/handle/2451/61215). To process the downloaded links in parallel, run
    ```sh
    $ python process.py --link_data_dir {path of the downloaded data}
    ```
  We collect data for our DeepCAD paper in this way.


### Reference
[Placeholder]
```
```