# CPDS
Cyber-Physical Dynamic System Modeling for Frequency Regulation and AGC Services of DES\
PI: Xin Fang NREL
### Env setup:
```
conda create --name oe36 python=3.6
conda activate oe36
conda install -c gmlc-tdc helics
(pip install helics==2.6.0.post0.dev0)

pip install OpenDSSDirect.py
git clone https://github.com/NREL/PyDSS.git
pip install -e .
```
### install andes
```
conda install andes
```

### install helics-cli
(for windows)
```
pip install git+git://github.com/GMLC-TDC/helics-cli.git@python-master
```

After running setup.py cosim can be launched in cli by (note: the setup.py has not been created to-date. All the framework has been done manually for now)
```
helics --verbose run --path runner_1a.json
```
