'use strict';
/* Self-contained SVG mascots for GREEN rank reveals (no emoji font dependencies).
 * The same emblem is used beside the reveal and in each final leaderboard row.
 * Place is a tournament result, never an index in the array of revealed teams.
 */
window.SochiRankMascots=(()=>{
  const labels={
    1:'Зевс с молнией',
    2:'Серебряный титан',
    3:'Бронзовый воин',
    4:'Покоритель вершины',
    5:'Опытный альпинист',
    6:'Бодрый восходитель',
    7:'Турист с рюкзаком',
    8:'Измотанный турист',
    9:'Бабушка без трости',
    10:'Хромая бабушка с тростью',
    11:'Улитка на старте'
  };
  const art={
    11: '<path d="M15 73Q18 61 33 63Q30 45 46 39Q70 27 77 49Q86 70 66 78H34Q17 80 15 73Z" fill="#a8b8a4" stroke="#37535b" stroke-width="3"/><circle cx="55" cy="57" r="20" fill="#d1b78d" stroke="#805f58" stroke-width="3"/><path d="M58 44Q75 44 71 61Q67 77 51 68Q40 61 52 53Q61 51 61 60" fill="none" stroke="#9d755e" stroke-width="4" stroke-linecap="round"/><path d="M29 63V43M40 63V42" stroke="#476d61" stroke-width="5" stroke-linecap="round"/><circle cx="29" cy="39" r="4" fill="#f6e4b3"/><circle cx="40" cy="39" r="4" fill="#f6e4b3"/><path d="M12 80h71" stroke="#ebcf9b" stroke-width="4" stroke-linecap="round"/>',
    10: '<path d="M29 82Q27 63 36 58H64Q76 70 71 83Z" fill="#8b5669" stroke="#402e47" stroke-width="3"/><circle cx="67" cy="27" r="13" fill="#e9e1d4" stroke="#a5a4a2" stroke-width="3"/><path d="M35 35Q32 20 50 18Q68 17 68 36L60 39L40 40Z" fill="#d3d5d5"/><ellipse cx="49" cy="42" rx="18" ry="20" fill="#eac3a3" stroke="#8b6663" stroke-width="2"/><path d="M30 40Q29 25 37 25" fill="none" stroke="#cbd1d1" stroke-width="8"/><g fill="none" stroke="#54454b" stroke-width="2.5"><circle cx="42" cy="43" r="6"/><circle cx="57" cy="43" r="6"/><path d="M48 42h3"/></g><path d="M44 55Q50 60 57 54" fill="none" stroke="#9d6663" stroke-width="2"/><path d="M24 60l-9 14" stroke="#eac3a3" stroke-width="7" stroke-linecap="round"/><path d="M16 72V89Q16 95 22 95" fill="none" stroke="#f4d08c" stroke-width="5" stroke-linecap="round"/><path d="M63 84l-4 11M43 84l-4 11" stroke="#4d4654" stroke-width="5" stroke-linecap="round"/>',
    9: '<path d="M28 83Q29 64 38 57H65Q75 68 73 83Z" fill="#73938b" stroke="#32555f" stroke-width="3"/><circle cx="66" cy="27" r="13" fill="#e7e4dc" stroke="#a8a6a4" stroke-width="3"/><ellipse cx="50" cy="43" rx="19" ry="20" fill="#eac4a4" stroke="#8c6a62" stroke-width="2"/><path d="M32 40Q30 20 48 20Q69 18 69 39L60 30Q43 37 34 37" fill="#d5d6d5" stroke="#9ba4a2" stroke-width="2"/><g fill="none" stroke="#51424a" stroke-width="2.5"><circle cx="42" cy="45" r="6"/><circle cx="58" cy="45" r="6"/><path d="M48 43h4"/></g><path d="M43 56Q51 62 59 55" fill="none" stroke="#a56d61" stroke-width="2"/><path d="M34 65L20 53L16 41M67 65l14-10 3-12" fill="none" stroke="#eac4a4" stroke-width="7" stroke-linecap="round"/><path d="M41 83l-4 12M63 83l4 12" stroke="#46565e" stroke-width="5" stroke-linecap="round"/>',
    8: '<path d="M28 82L36 58L66 59L76 82Z" fill="#9b736d" stroke="#4b4b56" stroke-width="3"/><path d="M33 59Q18 66 22 82" fill="none" stroke="#b9ad8b" stroke-width="11"/><ellipse cx="51" cy="42" rx="18" ry="21" fill="#e2b38e"/><path d="M33 40Q35 19 54 22Q68 25 69 37Z" fill="#8d7863"/><path d="M32 33Q53 25 75 37" fill="none" stroke="#d9aa72" stroke-width="8" stroke-linecap="round"/><path d="M38 47l11 3m6 0 9-4" stroke="#674b4b" stroke-width="3" stroke-linecap="round"/><path d="M46 60q6-7 12-2" fill="none" stroke="#986357" stroke-width="2.5"/><path d="M73 35Q86 42 82 53Q75 54 75 44Z" fill="#a4e0ee"/><path d="M36 70l-19 13" stroke="#d4a685" stroke-width="7" stroke-linecap="round"/>',
    7: '<path d="M27 84Q29 59 40 57H63Q74 66 74 84Z" fill="#a5aa75" stroke="#425b52" stroke-width="3"/><rect x="15" y="55" width="18" height="30" rx="6" fill="#a96758" stroke="#624957" stroke-width="3"/><ellipse cx="51" cy="41" rx="19" ry="20" fill="#edbf94"/><path d="M26 29h51l-8-8H36Z" fill="#a28364"/><rect x="34" y="17" width="34" height="15" rx="5" fill="#bb9b72"/><path d="M43 46h3m11 0h3" stroke="#48525d" stroke-width="3" stroke-linecap="round"/><path d="M45 55q7 6 14 0" fill="none" stroke="#a46c64" stroke-width="2"/><path d="M76 64L85 76" stroke="#edbf94" stroke-width="8" stroke-linecap="round"/>',
    6: '<path d="M24 82l13-29h28l13 29Z" fill="#669d90" stroke="#355f62" stroke-width="3"/><ellipse cx="51" cy="38" rx="18" ry="20" fill="#deb08b"/><path d="M34 32Q36 18 52 17Q65 20 68 33L56 26H42Z" fill="#4f605f"/><path d="M41 41l6 0m10 0 6 0" stroke="#323e46" stroke-width="3" stroke-linecap="round"/><path d="M46 51q6 7 12 0" fill="none" stroke="#8b5d58" stroke-width="2"/><path d="M26 63l-13 12M76 64l10-12" stroke="#e3b88d" stroke-width="8" stroke-linecap="round"/><path d="M14 74v22" stroke="#e8be83" stroke-width="5" stroke-linecap="round"/><path d="M33 58h35" stroke="#d2d7af" stroke-width="4"/>',
    5: '<path d="M23 86Q28 58 40 54H65Q76 61 80 86Z" fill="#ad534c" stroke="#5b4859" stroke-width="4"/><path d="M30 75l18 7 23-19" fill="none" stroke="#f4c687" stroke-width="4"/><circle cx="49" cy="39" r="19" fill="#e0b28e"/><path d="M28 38Q30 18 49 18Q72 19 71 39Z" fill="#d6bb7d" stroke="#695b58" stroke-width="3"/><rect x="29" y="34" width="42" height="8" rx="3" fill="#ba834e"/><path d="M42 45h5m12 0h5" stroke="#51515b" stroke-width="3" stroke-linecap="round"/><path d="M45 56Q51 59 57 55" fill="none" stroke="#a66a5f" stroke-width="2"/><path d="M80 57l12-21" stroke="#e0c49b" stroke-width="5" stroke-linecap="round"/><path d="M85 38l14-8" stroke="#d7dce0" stroke-width="5" stroke-linecap="round"/>',
    4: '<path d="M24 88L31 64L46 55L69 56L80 88Z" fill="#bd7a4d" stroke="#5f4d54" stroke-width="4"/><path d="M34 83l37-24" fill="none" stroke="#e9c68c" stroke-width="5"/><ellipse cx="51" cy="40" rx="19" ry="21" fill="#e7b18a"/><path d="M29 40Q25 19 51 17Q74 20 73 41Z" fill="#c2cdd0" stroke="#57636f" stroke-width="4"/><path d="M32 38h40" stroke="#ad5b55" stroke-width="6"/><path d="M42 48h6m10 0h6" stroke="#48515a" stroke-width="3"/><path d="M73 59L90 31" stroke="#dcb98a" stroke-width="6" stroke-linecap="round"/><path d="M80 32l17-10M80 32l13 13" stroke="#d7e7e9" stroke-width="6" stroke-linecap="round"/>',
    3: '<path d="M22 90Q25 62 39 57H64Q76 64 79 90Z" fill="#bd7757" stroke="#68434a" stroke-width="4"/><path d="M30 72l21-10 20 10" fill="none" stroke="#ebc88e" stroke-width="5"/><ellipse cx="49" cy="44" rx="17" ry="19" fill="#edbe94"/><path d="M26 43L27 24L39 15L64 15L74 28L73 44L62 35L36 35Z" fill="#a86646" stroke="#f3c287" stroke-width="3"/><path d="M42 45h5m8 0h5" stroke="#403b46" stroke-width="3"/><path d="M48 55h9" stroke="#8b6260" stroke-width="2"/><path d="M24 60l-12-8-8 11 7 15 13 8 11-8v-13Z" fill="#c99562" stroke="#fae1ad" stroke-width="4"/><path d="M82 78l9-32" stroke="#f5d49b" stroke-width="5" stroke-linecap="round"/>',
    2: '<path d="M17 90Q26 65 39 55H66Q79 68 86 90Z" fill="#8da7b2" stroke="#d8e5e5" stroke-width="4"/><path d="M31 76l19-11 22 11" fill="none" stroke="#f4e4c9" stroke-width="5"/><ellipse cx="51" cy="44" rx="18" ry="20" fill="#e7bb9c"/><path d="M26 44Q21 20 39 14H64Q82 24 74 45L62 34H38Z" fill="#cdd9df" stroke="#f6f4e5" stroke-width="3"/><path d="M49 13V4M39 17l-6-9M64 17l7-9" stroke="#ece9d0" stroke-width="5" stroke-linecap="round"/><path d="M42 45h6m9 0h6" stroke="#4b5860" stroke-width="3"/><path d="M45 56q6 5 12 0" fill="none" stroke="#9e706d" stroke-width="2"/><path d="M12 50l-9 17 11 19 22-8-3-19Z" fill="#b2ccd2" stroke="#eff6f0" stroke-width="4"/><path d="M11 67l16 1" stroke="#7b9fa9" stroke-width="4"/>',
    1: '<path d="M13 90Q18 66 36 58H68Q82 69 90 90Z" fill="#e8bc76" stroke="#fff0c0" stroke-width="4"/><path d="M32 62l18 22 21-22" fill="none" stroke="#fff7d9" stroke-width="8"/><path d="M28 46Q22 28 29 20Q37 11 49 15Q69 9 76 25Q82 39 73 57L62 70H37L26 56Z" fill="#eff0df" stroke="#c9cfcb" stroke-width="3"/><ellipse cx="51" cy="39" rx="18" ry="20" fill="#f4d3aa"/><path d="M27 36Q30 12 51 13Q74 14 77 34L65 27L52 23L36 30Z" fill="#f4f3e7"/><path d="M36 46l11-2m9 0 11 2" stroke="#4e5364" stroke-width="4" stroke-linecap="round"/><path d="M44 55l7 13 8-13" fill="#fff" stroke="#e5e4dc" stroke-width="2"/><path d="M32 17l7-9 12 9 12-9 8 9" fill="none" stroke="#ffe0a0" stroke-width="5" stroke-linecap="round"/><path d="M73 47L88 22L82 19L100 0L93 24L99 25L76 63Z" fill="#ffe69e" stroke="#fff6d4" stroke-width="3"/><path d="M14 80l8-26" stroke="#f4d3aa" stroke-width="9" stroke-linecap="round"/>'
  };
  const palette={
    1:['#f4cf93','#8e445b'],2:['#d9e6ea','#627b8b'],3:['#d8ac84','#945f56'],
    4:['#dcc1a0','#a16d58'],5:['#d0c7ad','#8e7768'],6:['#b3d4bf','#3d7f78'],
    7:['#c6d4ad','#677b62'],8:['#c7c0b4','#8e7372'],9:['#ddd6cb','#8f7380'],
    10:['#c8bdc4','#795964'],11:['#b8d2c7','#507472']
  };
  function label(place){return labels[place]||'Участник восхождения'}
  function render(place){
    const rank=Number(place);
    const shades=palette[rank]||palette[11];
    const drawing=art[rank]||art[11];
    const description=label(rank);
    const safeLabel=description.replaceAll('&','&amp;').replaceAll('"','&quot;');
    return '<span class="gs-rank-symbol gs-rank-symbol-'+rank+'" role="img" aria-label="'+safeLabel+'" title="'+safeLabel+'">'
      +'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" focusable="false" aria-hidden="true">'
      +'<circle cx="50" cy="50" r="48" fill="'+shades[1]+'" stroke="'+shades[0]+'" stroke-width="3"/>'
      +'<path d="M10 60Q20 13 63 6Q83 9 92 29Q56 4 24 44Z" fill="'+shades[0]+'" opacity=".24"/>'
      +'<circle cx="50" cy="50" r="43" fill="none" stroke="#fff4d4" opacity=".24" stroke-width="1.5"/>'
      +drawing+'</svg></span>';
  }
  return {render,label};
})();
