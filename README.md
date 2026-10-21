# CPDS
Cyber-Physical Dynamic System Modeling for Frequency Regulation and AGC Services of DES\


PI: Xin Fang\
Contributor: Wenbo Wang

### Reference paper

If you use this framework in your research, please cite:

W. Wang, X. Fang, H. Cui, F. Li, Y. Liu, and T. J. Overbye,
"Transmission-and-Distribution Dynamic Co-Simulation Framework for Distributed
Energy Resource Frequency Response," *IEEE Transactions on Smart Grid*,
vol. 13, no. 1, pp. 482-495, January 2022.
DOI: [10.1109/TSG.2021.3118292](https://doi.org/10.1109/TSG.2021.3118292).
[IEEE Xplore](https://ieeexplore.ieee.org/abstract/document/9569771).

```bibtex
@article{wang2022tdcosimulation,
  author  = {Wang, Wenbo and Fang, Xin and Cui, Hantao and Li, Fangxing and Liu, Yijing and Overbye, Thomas J.},
  title   = {Transmission-and-Distribution Dynamic Co-Simulation Framework for Distributed Energy Resource Frequency Response},
  journal = {IEEE Transactions on Smart Grid},
  year    = {2022},
  volume  = {13},
  number  = {1},
  pages   = {482--495},
  month   = jan,
  doi     = {10.1109/TSG.2021.3118292}
}
```

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
git fetch --all
git reset --hard origin/master
```

### Local configuration

The optional standalone scripts construct paths with `pathlib.Path`, anchored to
`__file__`, so model paths do not depend on the terminal's working directory.
No environment variables are required for these paths.

| Script | Expected location relative to the CPDS repository root |
| --- | --- |
| `Algorithm_utils/vsm_test.py` | `Distribution/J1/Master.dss` and the J1 feeder's supporting files (not included) |
| `Transmission/Transmission_test.py` | `Transmission/network_model/ieee39.xlsx` (not included) |
| `Colse_loop_ACPF_cyber.py` | `Transmission/network_model/t3ps.raw` (included) |
| `Colse_loop_ACPF_cyber.py` | `.local/Austin/` containing the external DSS dataset, including `P5U/p5uhs2_1247/Master.dss` (not included) |
| `Colse_loop_ACPF_cyber.py` | `.local/18_bus/` containing the external scheduling dataset, including `ToGenerateUC&EDInput/` (not included) |

Place the missing model data at these locations before running the corresponding
script. The original J1 and IEEE 39-bus model choices are preserved. The legacy
Austin script also requires external Python modules that are not bundled here.
Paths passed to legacy APIs are converted to strings where needed.

Keep credentials and unpublished data in `.env`, `private/`, or `.local/`, which
are ignored by Git. The `Distribution/J1/` and `ieee39.xlsx` locations are not
ignored; review any data placed there before adding it to Git. Notebook outputs
are cleared for sharing.
The legacy requirements file contains unpinned packages where local build paths
were removed; the original environment has not been reproduced or validated.
