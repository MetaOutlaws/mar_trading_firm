from types import SimpleNamespace
import numpy as np
import pytest
from bracket_rule import levels,raw_trade,independent_path

class Scan:
    def __init__(self,x,minimum=False):self.x=np.asarray(x);self.minimum=minimum
    def first(self,i,end,threshold):
        k=np.flatnonzero(self.x[i:end]<=threshold if self.minimum else self.x[i:end]>=threshold)
        return i+int(k[0]) if len(k) else end

def tape(o,h,l,c):
    return SimpleNamespace(o=np.array(o,float),h=np.array(h,float),l=np.array(l,float),cl=np.array(c,float),lo=Scan(l,True),hi=Scan(h))

@pytest.mark.parametrize('side',[1,-1])
@pytest.mark.parametrize('slip',[0,.0005,.001,.002])
def test_fill_level_origin(side,slip):
    a=levels(100,side,slip,'quote_brackets');b=levels(100,side,slip,'fill_brackets')
    assert a['entry_fill']==b['entry_fill']==100*(1+side*slip)
    assert np.isclose(b['stop_price']/a['stop_price'],1+side*slip)
    assert np.isclose(b['target_price']/a['target_price'],1+side*slip)
    if not slip:assert a==b

@pytest.mark.parametrize('side',[1,-1])
@pytest.mark.parametrize('arm',['quote_brackets','fill_brackets'])
def test_tie_stop_first(side,arm):
    t=tape([100],[104],[96],[100]);r=raw_trade(t,0,side,.001,1,arm)
    assert r['reason']=='stop' and r['ambiguous'];independent_path(t,r,side,.001,1,arm)

@pytest.mark.parametrize('side',[1,-1])
def test_adverse_gap(side):
    t=tape([100,95 if side==1 else 105],[100.1,95.2 if side==1 else 105.2],[99.9,94.8 if side==1 else 104.8],[100,95 if side==1 else 105])
    r=raw_trade(t,0,side,.002,2,'fill_brackets');assert r['reason']=='stop' and r['quote']==t.o[1]
    independent_path(t,r,side,.002,2,'fill_brackets')

@pytest.mark.parametrize('side',[1,-1])
def test_first_hit_and_boundary(side):
    t=tape([100,100,100],[100.1,103,104],[99.9,97,96],[100,100,100])
    r=raw_trade(t,0,side,.001,1,'fill_brackets');assert r['reason']=='boundary_mtm' and r['exit_i']==0 and r['fund_mode']=='close'
    independent_path(t,r,side,.001,1,'fill_brackets')
    r=raw_trade(t,0,side,.001,3,'fill_brackets');assert r['exit_i']==1 and r['reason']=='stop'
    independent_path(t,r,side,.001,3,'fill_brackets')

@pytest.mark.parametrize('side',[1,-1])
def test_quote_target_becomes_fill_stop(side):
    t=(tape([100,100],[102.55,100.1],[99.9,97.9],[102.5,98]) if side==1 else
       tape([100,100],[100.1,102.1],[97.45,99.9],[97.5,102]))
    a=raw_trade(t,0,side,.002,2,'quote_brackets');b=raw_trade(t,0,side,.002,2,'fill_brackets')
    assert a['reason']=='target' and b['reason']=='stop'
    independent_path(t,a,side,.002,2,'quote_brackets');independent_path(t,b,side,.002,2,'fill_brackets')

@pytest.mark.parametrize('side',[1,-1])
def test_zero_slip_same_path(side):
    t=tape([100,101],[101,103],[99,100],[100,102])
    assert raw_trade(t,0,side,0,2,'quote_brackets')==raw_trade(t,0,side,0,2,'fill_brackets')

@pytest.mark.parametrize('args',[(0,1,.001,'fill_brackets'),(100,0,.001,'fill_brackets'),(100,1,-.001,'fill_brackets'),(100,1,.02,'fill_brackets'),(100,1,.001,'unknown')])
def test_invalid(args):
    with pytest.raises(ValueError):levels(*args)
