# CPDS
Cyber-Physical Dynamic System Modeling for Frequency Regulation and AGC Services of DES\
PI: Xin Fang NREL

### Related repos
CPDS_setup: https://github.nrel.gov/wwang2/CPDS_setup \
CPDS_Texas2k: https://github.nrel.gov/wwang2/CPDS_Texas2k

### Env setup: install HELICS, Opendssdirect, etc.
```
conda create --name oe36 python=3.6
conda activate oe36
# conda install -c gmlc-tdc helics
# pip install helics==2.6.0.post0.dev0
pip install helics==2.7.1

pip install OpenDSSDirect.py
# git clone https://github.com/NREL/PyDSS.git
# pip install -e .
pip install seaborn

# install ANDES in dev mode
git clone https://github.com/cuihantao/andes
python setup.py develop
pip install -e .
andes prepare
```

Check helics version
```
python
import helics as h
h.__version__
```
### NOTES: HELICS 2.6.0 and newer should work, but newer versions have not been tested.

install helics-cli
(for windows and mac)
```
pip install git+git://github.com/GMLC-TDC/helics-cli.git@main
```

install andes (not in dev mode, ignore this if you have installed ANDES in dev mode)
```
conda install andes
andes prepare
```
Notes: if you installed ANDES in dev mode through downloading the latest version of andes from GitHub repository and install from the local folder, (the advantage is the getting latest version before release), using pip update can't include the latest code development in ANDES.

This is for ANDES dependences
```
pip install openpyxl
```

Install pulp for distribution voltage-power sensitivity matrix and optimization
```
pip install pulp
```


### Launch CPDS cosimulation

cosim can be launched in Terminal using HELICS cli tool by the command
```
helics --verbose run --path runner.json
```

### Results and figures

Results are stored in the csv files in federates folders, a notebook file is created to read results.
Figures are stored in the results_figure folder


### Hard pull in git
```
git reset --hard origin/master
git fetch --all
```
