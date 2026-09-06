"""Own-data figures and strict selection of the one-pass baseline."""
import contextlib
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import pandas as pd
import pytest

from tests.test_cohort_notebook import _load_notebook


@pytest.fixture(scope='module')
def nb():
    with contextlib.redirect_stdout(io.StringIO()):
        return _load_notebook()


def test_all_modes_export_individual_values_and_vector_figure(nb, tmp_path):
    rows=[]
    for mode, (_, metric, _) in nb.THESIS_HEADLINES.items():
        for i in range(3):
            rows.append(dict(participant=f'P{i+1:02}', phase='battery', mode=mode,
                             metric=metric, value=.6+i*.1, hand_role='both',
                             config_hash='abc', block_folder='sample', n_trials=10))
    rows.append({**rows[0], 'phase':'pre', 'value':999})
    cohort=dict(long=pd.DataFrame(rows), out_dir=tmp_path, tables={})
    nb.FIGDIR=tmp_path/'figures';nb._FIGS_CLEARED=False
    nb.plt.show=lambda:None
    result=nb.sec_thesis_overview(cohort)
    assert len(result['values'])==30
    assert result['values']['mode'].nunique()==10
    assert result['values']['value'].max()<999
    assert (tmp_path/'thesis_overview.pdf').stat().st_size>1000
    assert (tmp_path/'thesis_overview.svg').stat().st_size>1000
    assert len(pd.read_csv(tmp_path/'thesis_overview_values.csv'))==30
    nb.plt.close('all')


def test_missing_data_is_not_zero(nb):
    frame=pd.DataFrame([dict(participant='P01', phase='battery', mode='reaction',
                           metric='median_rt_ms', value=float('nan'))])
    assert nb.thesis_overview_rows({'long':frame}).empty


def test_old_phases_and_ambiguous_repeats_are_excluded(nb, tmp_path):
    cat=[]
    for i,(who,phase,mode) in enumerate([('P01','pre','reaction'),
            ('P02','battery','reaction'),('P02','battery','reaction'),
            ('P03','battery','echo'),('P03','','echo')]):
        folder=tmp_path/str(i);folder.mkdir()
        meta=dict(visit='1', dominant_hand='right',block_summary={'status':'completed'},
                  battery={'phase':phase})
        (folder/'metadata.json').write_text(json.dumps(meta))
        cat.append(dict(who=who,folder=str(folder),day='2026-09-06',mode=mode,hand='right'))
    selected,dropped=nb.cohort_catalogue(pd.DataFrame(cat))
    assert dropped['old_phase']==1
    assert dropped['ambiguous_repeat']==2
    assert list(selected['participant'])==['P03','P03']
    assert set(selected['phase'])=={'battery',''}


def test_simons_span_has_no_corsi_reference_line(nb):
    assert nb.COHORT_METRICS[('echo','span')]['ref'] is None


def test_different_task_configurations_do_not_pool(nb, tmp_path):
    cat=[]
    for i,window in enumerate([1.,2.]):
        folder=tmp_path/str(i);folder.mkdir()
        meta=dict(visit='1',block_summary={'status':'completed'},
                  battery={'phase':'battery'},config_snapshot={'reaction':{'window':window}})
        (folder/'metadata.json').write_text(json.dumps(meta))
        cat.append(dict(who=f'P{i+1:02}',folder=str(folder),day='2026-09-06',mode='reaction',hand='right'))
    selected,dropped=nb.cohort_catalogue(pd.DataFrame(cat))
    assert selected.empty
    assert dropped['mixed_configuration']==2
