document.querySelectorAll('[data-copy]').forEach(function(btn){
  btn.addEventListener('click',function(){
    var url=btn.getAttribute('data-copy'),msg=btn.querySelector('.share-copied');
    var done=function(){msg.textContent='Link copied';btn.classList.add('copied');setTimeout(function(){msg.textContent='';btn.classList.remove('copied');},2000);};
    if(navigator.clipboard){navigator.clipboard.writeText(url).then(done,function(){prompt('Copy this link:',url);});}
    else{prompt('Copy this link:',url);}
  });
});
