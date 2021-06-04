# CPDS
Cyber-Physical Dynamic System Modeling for Frequency Regulation and AGC Services of DES\
PI: Xin Fang NREL
### Env setup: install HELICS, Opendssdirect, etc.
```
conda create --name oe36 python=3.6
conda activate oe36
# conda install -c gmlc-tdc helics
pip install helics==2.6.0.post0.dev0

pip install OpenDSSDirect.py
# git clone https://github.com/NREL/PyDSS.git
# pip install -e .

# install ANDES in dev mode
git clone https://github.com/cuihantao/andes
python setup.py develop
pip install -e .
```
### install andes
```
conda install andes
```
Download the latest version of andes from GitHub repository and install from the local folder since the latest version hasn't been released. Using pip update can't include the latest code development in ANDES.


### install helics-cli
(for windows and mac)
```
pip install git+git://github.com/GMLC-TDC/helics-cli.git@python-master
```

Install pulp for distribution voltage-power sensitivity matrix and optimization
```
pip install pulp
```
This is for ANDES dependences
```
pip install openpyxl
```
Check helics version
```
python
import helics as h
h.__version__
```
### NOTES: HELICS 2.6.0 and newer should work, but newer versions have not been tested.

After running setup.py cosim can be launched in cli by (note: the setup.py has not been created to-date. All the framework has been done manually for now)
```
helics --verbose run --path runner.json
```


### Results and figures

Results are (for now) in the log files, a notebook file is created to read results.
Figures are stored in the results_figure folder


### Hard pull in git
```
git reset --hard origin/master
git fetch --all
```
