import unittest
import numpy as np
from PIL import Image
from ascii_pipeline import convert, glyph_atlas, CHARSET, BOLD_FONT_PATH


class TonalTests(unittest.TestCase):
    def test_brightness_survives_and_can_reconstruct_without_photo(self):
        x = np.tile(np.linspace(20,235,320,dtype=np.uint8), (160,1))
        source = Image.fromarray(np.stack([x,np.flip(x,axis=1),x],axis=2))
        data, mono, color = convert(source,columns=32,font_path=BOLD_FONT_PATH,renderer='tonal')
        cw,ch=data['cell_width'],data['cell_height'];rows=data['rows'];cols=data['columns']
        means=np.asarray(color).reshape(rows,ch,cols,cw,3).mean(axis=(1,3))
        # The old fixed-background renderer loses large amounts of cell brightness.
        self.assertLess(np.abs(means-np.array(data['colors'])).max(), 0.6)
        masks,_,_=glyph_atlas(BOLD_FONT_PATH)
        for kind,render in [('color',color),('mono',mono)]:
            rebuilt=np.empty((rows*ch,cols*cw,3 if kind=='color' else 1),dtype=np.uint8)
            styles=data['cell_styles'][kind]
            for y,line in enumerate(data['lines']):
                for x,char in enumerate(line):
                    bg=np.array(styles['background'][y][x]);fg=np.array(styles['foreground'][y][x])
                    rebuilt[y*ch:(y+1)*ch,x*cw:(x+1)*cw]=np.rint(bg+masks[CHARSET.index(char)][:,:,None]*(fg-bg))
            expected=np.asarray(render)
            if kind=='mono': rebuilt=rebuilt[:,:,0]
            self.assertTrue(np.array_equal(rebuilt,expected))

    def test_flat_extremes(self):
        for value in (0,255):
            _,mono,color=convert(Image.new('RGB',(80,80),(value,)*3),columns=16,renderer='tonal')
            self.assertTrue(np.all(np.asarray(color)==value))
            self.assertTrue(np.all(np.asarray(mono)==value))


if __name__=='__main__': unittest.main()
