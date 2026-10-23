{# 学校库的前端筛选脚本（构建期注入数据） #}
const DATA = {{ schools_json | safe }};
const ALL_DISTRICTS = {{ districts_json | safe }};
const state = { q: new URLSearchParams(location.search).get('q') || '', lv:'', dist:'', type:'' };
const grid = document.getElementById('grid'), cnt = document.getElementById('count');

function esc(s){
  return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}

/* 生成筛选按钮组：使用 aria-pressed 表达选中态，键盘可达 */
function chips(elId, key, values, allLabel){
  const box = document.getElementById(elId);
  const pairs = [['', allLabel]].concat(values.map(function(v){ return [v, v]; }));
  pairs.forEach(function(pair){
    const v = pair[0], label = pair[1];
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip' + (v === state[key] ? ' on' : '');
    b.setAttribute('aria-pressed', String(v === state[key]));
    b.textContent = label;
    b.dataset.v = v;
    b.addEventListener('click', function(){
      state[key] = v;
      Array.prototype.forEach.call(box.children, function(c){
        const on = c.dataset.v === v;
        c.classList.toggle('on', on);
        c.setAttribute('aria-pressed', String(on));
      });
      render();
    });
    box.appendChild(b);
  });
}

function render(){
  const q = state.q.trim().toLowerCase();
  const rows = DATA.filter(function(s){
    if(state.lv && s.level !== state.lv) return false;
    if(state.dist && s.district !== state.dist) return false;
    if(state.type && s.type !== state.type) return false;
    if(q){
      const hay = (s.name + ' ' + (s.short || '') + ' ' + (s.tier || '') + ' '
                  + (s.tagline || '') + ' ' + s.district).toLowerCase();
      if(hay.indexOf(q) === -1) return false;
    }
    return true;
  });
  cnt.textContent = '匹配 ' + rows.length + ' 所 / 共 ' + DATA.length + ' 所';
  if(!rows.length){
    grid.innerHTML = '<div class="empty">没有匹配的学校，试试换个关键词或清空筛选。</div>';
    return;
  }
  grid.innerHTML = rows.map(function(s){
    const t = s.type === '民办' ? 'b-pri' : 'b-pub';
    return '<div class="card">'
      + '<h3><a href="' + s.url + '">' + esc(s.name) + '</a></h3>'
      + '<div class="badges">'
      +   '<span class="b b-lv">' + esc(s.level) + '</span>'
      +   '<span class="b ' + t + '">' + esc(s.type) + '</span>'
      +   '<span class="b b-d">' + esc(s.district) + '</span>'
      +   (s.short ? '<span class="b b-d">' + esc(s.short) + '</span>' : '')
      + '</div>'
      + '<div class="tier">' + esc(s.tier || '') + '</div>'
      + '<div class="tag">' + esc(s.tagline || '') + '</div>'
      + '<a class="more" href="' + s.url + '">查看完整档案 →</a>'
      + '</div>';
  }).join('');
}

document.getElementById('q').value = state.q;
document.getElementById('q').addEventListener('input', function(e){
  state.q = e.target.value; render();
});
chips('f-lv', 'lv', ['小学','初中','高中'], '全部学段');
chips('f-dist', 'dist', ALL_DISTRICTS, '全部区');
chips('f-type', 'type', ['公办','民办'], '不限性质');
render();
