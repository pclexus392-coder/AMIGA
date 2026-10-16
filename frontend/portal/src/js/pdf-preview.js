import {getDocument,GlobalWorkerOptions} from '../../vendor/pdfjs/pdf.mjs';
GlobalWorkerOptions.workerSrc=new URL('../../vendor/pdfjs/pdf.worker.mjs',import.meta.url).href;
export async function previewPDF(bytes,container) {
  container.replaceChildren();const hint=document.createElement('p');hint.className='subtle';hint.textContent='Memuat halaman PDF…';container.append(hint);
  try{
    const pdf=await getDocument({data:bytes.slice(),isEvalSupported:false,useSystemFonts:true}).promise;
    if(!container.isConnected){await pdf.destroy();return;}
    container.replaceChildren();
    for(let pageNo=1;pageNo<=pdf.numPages;pageNo++){
      if(!container.isConnected)break;
      const page=await pdf.getPage(pageNo),base=page.getViewport({scale:1});
      const scale=Math.min(1.8,Math.max(.7,(container.clientWidth-30)/base.width)),viewport=page.getViewport({scale});
      const canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width*1.5);canvas.height=Math.ceil(viewport.height*1.5);canvas.style.width=`${viewport.width}px`;canvas.style.height=`${viewport.height}px`;canvas.setAttribute('role','img');canvas.setAttribute('aria-label',`Halaman PDF ${pageNo} dari ${pdf.numPages}`);container.append(canvas);
      await page.render({canvasContext:canvas.getContext('2d'),viewport,transform:[1.5,0,0,1.5,0,0]}).promise;
      const pageHint=document.createElement('p');pageHint.className='subtle';pageHint.textContent=`Halaman ${pageNo} / ${pdf.numPages}`;container.append(pageHint);
    }
    await pdf.destroy();
  }catch(e){hint.textContent=`PDF tidak dapat dirender: ${e.message}. Gunakan tautan PDF asli atau coba kembali.`;container.replaceChildren(hint);throw e;}
}
