import {state} from '../stores/session.js';import {esc} from '../utils/html.js';import {badge} from '../components/common/status.js';import {table} from '../components/common/table.js';import {field} from '../components/common/fields.js';import {WINDOW_STATES,GAP_REASONS} from '../constants/enums.js';
const pct=x=>x===null||x===undefined?'—':(x*100).toFixed(1)+'%';
const num=x=>x===null||x===undefined?'—':x;
function weekCell(d){return d?`${d.reading_count}篇 / ${pct(d.completion)} / ${pct(d.night_share)}<br><span class="eyebrow">${esc(d.source)}</span>`:'<span class="muted">缺报</span>'}
function profileTable(w){
 const weeks=w.result.window_weeks.map(x=>x.week);
 const heads=['会员编号','状态',...weeks.map(k=>k.slice(5)),'总阅读','加权完读率','加权夜读占比'];
 const rows=w.result.profiles.map(p=>[p.code,p.status==='qualified'?'合格':'缺口',
  ...p.weeks.map(weekCell),num(p.total_reading),pct(p.weighted_completion),pct(p.weighted_night_share)]);
 return `<h3>会员周明细（窗口内按周号，每格为 阅读篇数 / 完读率 / 夜读占比）</h3><div class=scroll><table><thead><tr>${heads.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(v=>`<td>${v}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
}
function gapPanel(w){
 const gaps=w.gaps||[];
 if(!gaps.length)return '<p class="notice">本窗口没有缺口会员，全部会员四周完整。</p>';
 return `<h3>缺口清单（不补零、不参与聚类）</h3>${table(['会员编号','缺口原因','有效周数','缺失自然周','阅读合计'],gaps.map(g=>[g.code,GAP_REASONS[g.gap_reason]||g.gap_reason,g.present_weeks,(g.missing_weeks||[]).join(', ')||'—',num(g.total_reading)]))}`
}
function reconcile(w){
 const r=w.result.reconciliation;
 return `<h3>汇总对账</h3><div class="metrics"><div><strong>${r.reader_total}</strong>档案会员</div><div><strong>${r.qualified}</strong>合格（四周完整）</div><div><strong>${r.gaps}</strong>缺口会员</div><div><strong>${r.total_reading}</strong>窗口总阅读篇数</div><div><strong>${r.reading_matched?'一致':'不一致'}</strong>周明细求和对账</div><div><strong>${r.matched?'平账':'不平'}</strong>合格+缺口=会员数</div></div><p class="notice">输入校验和 <code>${esc(w.result.input_checksum.slice(0,16))}…</code>，重复计算结果保持一致。来源分布：${esc(Object.entries(r.source_reading).map(([k,v])=>`${k}=${v}`).join(' / ')||'无')}</p>`
}
export function render(){
 const w=state.selectedWindow;
 const published=state.windows.filter(x=>x.state==='published');
 const canWrite=state.user.role!=='viewer';
 return `<div class="split"><section class="panel"><div class="result-head"><h2>四周窗口画像 ${w?badge(WINDOW_STATES[w.state]||w.state):''}</h2>${w?'<button id="refresh">刷新窗口</button>':''}</div>${w?`
  <p class="notice">锚点周 <b>${esc(w.anchor_week)}</b>，覆盖 ${w.result?w.result.window_weeks.map(x=>x.week).join(' → '):''}。${esc(w.result?w.result.gap_policy:'')}</p>
  ${w.state==='failed'?`<p class="error">${esc(w.error)}</p>`:''}
  ${w.result?reconcile(w):''}
  ${w.result?profileTable(w):''}
  ${w.result?gapPanel(w):''}
  <div class="actions">
   ${canWrite&&w.state!=='published'?`<button data-window-build="${w.id}">重新计算（幂等）</button>`:''}
   ${state.user.role==='admin'&&w.state==='ready'?`<button data-window-publish="${w.id}" class="primary">发布该窗口</button>`:''}
   ${w.state==='published'?`<p class="notice">已发布于 ${esc((w.published_at||'').slice(0,16))}，窗口内各周已冻结。新分群、群成员与触达草案均指向本窗口。</p>`:''}
   <button data-window-export="${w.id}">导出窗口 JSON</button>
  </div>`:'<p class="notice">右侧选择一个已结束自然周作为锚点，创建四周窗口；计算完成后由负责人发布。</p>'}
  <h3>窗口版本</h3>${state.windows.map(x=>`<button class="study" data-window="${x.id}">#${x.id} ${esc(x.anchor_week)} · ${esc(WINDOW_STATES[x.state]||x.state)}${x.gap_count?` · 缺口${x.gap_count}`:''}</button>`).join('')||'<p>尚无窗口。</p>'}
  ${published.length?`<p class="notice">当前线上窗口：#${published[0].id} ${esc(published[0].anchor_week)}（发布前的分群只能引用上一版已发布窗口）。</p>`:''}
 </section><aside class="side"><h2>新建四周窗口</h2><form id="window">${field('锚点周 YYYY-Www（须已结束）','anchor_week','text','required placeholder=2026-W46')}<button class="primary" ${canWrite?'':'disabled'}>创建并排队计算</button></form><p class="eyebrow">窗口 = 锚点周及其向前连续四个自然周。不足四周或四周零阅读的会员进入缺口清单而非补零。</p></aside></div>`}
