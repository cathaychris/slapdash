from slapdash import run

try:
    from tiqi_ad5371 import AD5371
except ImportError:
    print('tiqi-ad5371 not installed. Please run \'pip install git+https://gitlab.phys.ethz.ch/tiqi-projects/drivers/tiqi-ad5371\'')
    raise SystemExit(1)

if __name__ == '__main__':
    dac = AD5371()
    run(dac)
