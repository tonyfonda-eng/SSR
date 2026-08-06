    <script>
        fetch('realtime_audit.json')
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById('auditTableBody');
                const metrics = data.source_metrics || [];
                if (metrics.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px;">No audit metrics available for today.</td></tr>';
                    return;
                }
                tbody.innerHTML = '';
                metrics.forEach(m => {
                    const tr = document.createElement('tr');
                    const emHtml = m.emergency_stop ? `<span class="badge danger">YES (${m.reason})</span>` : '<span class="badge success">NO</span>';
                    let gradeColor = 'inherit';
                    if (m.grade.startsWith('A')) gradeColor = 'var(--green)';
                    else if (m.grade === 'F') gradeColor = 'var(--red)';
                    else if (m.grade === 'D') gradeColor = 'var(--yellow)';
                    
                    tr.innerHTML = `
                        <td style="font-weight:bold;">${m.source}</td>
                        <td>${m.mode}</td>
                        <td style="color:${gradeColor}; font-weight:bold;">${m.grade}</td>
                        <td>${m.status_light}</td>
                        <td class="metric-val">${m.raw}</td>
                        <td class="metric-val">${m.avg_30d}</td>
                        <td class="metric-val" style="color:${m.dev_pct < -30 ? 'var(--red)' : (m.dev_pct > 30 ? 'var(--green)' : 'inherit')}">${m.dev_pct > 0 ? '+' : ''}${m.dev_pct}%</td>
                        <td class="metric-val">${m.lifetime_rel}%</td>
                        <td>${emHtml}</td>
                    `;
                    tbody.appendChild(tr);
                });
            })
            .catch(err => {
                console.error("Failed to load audit metrics:", err);
                document.getElementById('auditTableBody').innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--red);">Error loading audit metrics.</td></tr>';
            });
            
        let screeningData = [];
        let filteredData = [];
        let selectedDate = new Date().toISOString().split('T')[0];

        fetch('screening_log.json')
            .then(res => res.json())
            .then(data => {
                const allData = Array.isArray(data) ? data : (data.screening_log || []);
                window.allData = allData;
                
                // Populate Dates
                const dates = [...new Set(allData.map(r => r.timestamp ? r.timestamp.substring(0, 10) : null).filter(Boolean))].sort().reverse();
                const dateSel = document.getElementById('dateFilter');
                dates.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d; opt.textContent = d;
                    dateSel.appendChild(opt);
                });
                
                if (dates.length > 0 && !dates.includes(selectedDate)) {
                    selectedDate = dates[0];
                } else if (dates.length === 0) {
                    selectedDate = '';
                }
                
                if (selectedDate) {
                    dateSel.value = selectedDate;
                }

                filterByDate();
            })
            .catch(err => {
                screeningData = [];
                renderTable();
            });

        function filterByDate() {
            selectedDate = document.getElementById('dateFilter').value;
            if (selectedDate) {
                screeningData = window.allData.filter(r => r.timestamp && r.timestamp.startsWith(selectedDate));
            } else {
                screeningData = window.allData;
            }
            populateFilters();
            renderTable();
        }

        function populateFilters() {
            const sourceSel = document.getElementById('sourceFilter');
            sourceSel.innerHTML = '<option value="">All Sources</option>';
            const sources = [...new Set(screeningData.map(r => r.source).filter(Boolean))].sort();
            sources.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s; opt.textContent = s;
                sourceSel.appendChild(opt);
            });
            
            const reasonSel = document.getElementById('reasonFilter');
            reasonSel.innerHTML = '<option value="">All Reasons</option>';
            const reasons = [...new Set(screeningData.map(r => r.drop_reason).filter(Boolean))].sort();
            reasons.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r; opt.textContent = r;
                reasonSel.appendChild(opt);
            });
        }

        document.getElementById('dateFilter').addEventListener('change', filterByDate);

        document.getElementById('sourceFilter').addEventListener('change', renderTable);
        document.getElementById('reasonFilter').addEventListener('change', renderTable);
        document.getElementById('outcomeFilter').addEventListener('change', renderTable);
        document.getElementById('searchBox').addEventListener('input', renderTable);

        function showModal(idx) {
            const r = filteredData[idx];
            if (!r) return;
            document.getElementById('modalTitle').textContent = r.headline || 'Untitled';
            document.getElementById('modalMeta').innerHTML = `<strong>Source:</strong> ${r.source || 'Unknown'} | <strong>Company:</strong> ${r.company_name || 'UNKNOWN'} | <a href="${r.url || '#'}" target="_blank" style="color:var(--blue)">Original Link</a>`;
            document.getElementById('modalBody').textContent = r.body_snippet || 'No article body available.';
            document.getElementById('articleModal').style.display = "block";
        }
        function closeModal() {
            document.getElementById('articleModal').style.display = "none";
        }
        window.onclick = function(event) {
            if (event.target == document.getElementById('articleModal')) {
                closeModal();
            }
        }

        function renderTable() {
            const tbody = document.getElementById('tableBody');
            const sourceVal = document.getElementById('sourceFilter').value;
            const reasonVal = document.getElementById('reasonFilter').value;
            const outcomeVal = document.getElementById('outcomeFilter').value;
            const searchVal = document.getElementById('searchBox').value.toLowerCase();

            filteredData = screeningData.filter(r => {
                if (sourceVal && r.source !== sourceVal) return false;
                if (reasonVal && r.drop_reason !== reasonVal) return false;
                if (outcomeVal && r.outcome !== outcomeVal) return false;
                if (searchVal) {
                    const hay = `${r.headline||''} ${r.source||''}`.toLowerCase();
                    if (!hay.includes(searchVal)) return false;
                }
                return true;
            });

            document.getElementById('resultCount').textContent = `Showing ${filteredData.length} of ${screeningData.length} articles for today (${selectedDate || 'All Dates'})`;

            tbody.innerHTML = '';
            if (filteredData.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px;">No articles match the current filters.</td></tr>';
                return;
            }

            filteredData.forEach((r, idx) => {
                const tr = document.createElement('tr');
                const outcomeCls = r.outcome === 'PASSED' ? 'outcome-passed' : 'outcome-dropped';
                const reasonHtml = r.drop_reason ? `<span class="reason-tag">${r.drop_reason}</span>` : '';
                const modeCls = r.ingestion_mode === 'HTML_FALLBACK' ? 'mode-fallback' : 'mode-rss';
                const modeLabel = r.ingestion_mode === 'HTML_FALLBACK' ? 'FALLBACK' : (r.ingestion_mode || 'RSS');
                
                const statusHtml = r.drop_reason === 'dropped_hash_duplicate' 
                    ? '<span class="badge warn">DUPLICATE</span>' 
                    : '<span class="badge success">BRAND NEW</span>';
                
                tr.innerHTML = `<td>${r.timestamp || ''}</td>
                                <td>${statusHtml}</td>
                                <td style="font-weight:bold; color:var(--blue);">${r.company_name || 'UNKNOWN'}</td>
                                <td>${r.source || 'Unknown'}</td>
                                <td class="headline-cell"><a href="javascript:void(0)" onclick="showModal(${idx})" title="${(r.headline||'').replace(/"/g,'&quot;')}">${r.headline || 'Untitled'}</a></td>
                                <td class="${modeCls}">${modeLabel}</td>
                                <td class="${outcomeCls}">${r.outcome || ''}</td>
                                <td>${r.final_stage || ''}</td>
                                <td>${reasonHtml}</td>`;
                tbody.appendChild(tr);
            });
        }
    </script></body></html>