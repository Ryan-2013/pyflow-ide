"""
Go 標準函式庫符號資料庫 — 常用套件的函式、型別、常數。
用於 IntelliSense 補全與 hover 提示。
"""

def _f(name, sig, params, ret, doc):
    return {'name':name,'kind':'function','sig':sig,'params':params,'ret':ret,'doc':doc}

def _t(name, sig, doc):
    return {'name':name,'kind':'class','sig':sig,'params':[],'ret':None,'doc':doc}

def _v(name, sig, doc):
    return {'name':name,'kind':'variable','sig':sig,'params':[],'ret':None,'doc':doc}

GO_PACKAGES = {

'fmt': [
    _f('Println',    'fmt.Println(a ...any) (n int, err error)',                         ['a ...any'],                    '(int,error)', '輸出到 stdout，以空格分隔，末尾換行。'),
    _f('Printf',     'fmt.Printf(format string, a ...any) (n int, err error)',            ['format string','a ...any'],    '(int,error)', '格式化輸出到 stdout。'),
    _f('Print',      'fmt.Print(a ...any) (n int, err error)',                            ['a ...any'],                    '(int,error)', '輸出到 stdout，無換行。'),
    _f('Sprintf',    'fmt.Sprintf(format string, a ...any) string',                       ['format string','a ...any'],    'string',      '建立格式化字串。'),
    _f('Errorf',     'fmt.Errorf(format string, a ...any) error',                         ['format string','a ...any'],    'error',       '建立格式化 error（支援 %w 包裝）。'),
    _f('Sscanf',     'fmt.Sscanf(str, format string, a ...any) (n int, err error)',       ['str string','format string','a ...any'],'(int,error)', '從字串按格式解析。'),
    _f('Fprintln',   'fmt.Fprintln(w io.Writer, a ...any) (n int, err error)',            ['w io.Writer','a ...any'],      '(int,error)', '輸出到 w，末尾換行。'),
    _f('Fprintf',    'fmt.Fprintf(w io.Writer, format string, a ...any) (n int, err error)',['w io.Writer','format string','a ...any'],'(int,error)', '格式化輸出到 w。'),
    _f('Scan',       'fmt.Scan(a ...any) (n int, err error)',                             ['a ...any'],                    '(int,error)', '從 stdin 讀取空白分隔的值。'),
    _f('Scanf',      'fmt.Scanf(format string, a ...any) (n int, err error)',             ['format string','a ...any'],    '(int,error)', '按格式從 stdin 讀取。'),
    _f('Stringer',   'type fmt.Stringer interface { String() string }',                   [],                              None,          '實作此介面可自訂 fmt 輸出。'),
],

'os': [
    _f('Open',       'os.Open(name string) (*os.File, error)',                   ['name string'],                        '(*File,error)', '以唯讀模式開啟檔案。'),
    _f('Create',     'os.Create(name string) (*os.File, error)',                 ['name string'],                        '(*File,error)', '建立或截斷檔案（權限 0666）。'),
    _f('OpenFile',   'os.OpenFile(name string, flag int, perm fs.FileMode) (*File, error)', ['name string','flag int','perm fs.FileMode'], '(*File,error)', '以指定旗標開啟檔案。'),
    _f('ReadFile',   'os.ReadFile(name string) ([]byte, error)',                 ['name string'],                        '([]byte,error)', '讀取整個檔案。'),
    _f('WriteFile',  'os.WriteFile(name string, data []byte, perm fs.FileMode) error', ['name string','data []byte','perm fs.FileMode'], 'error', '將 data 寫入檔案。'),
    _f('Remove',     'os.Remove(name string) error',                             ['name string'],                        'error',         '刪除檔案或空目錄。'),
    _f('RemoveAll',  'os.RemoveAll(path string) error',                          ['path string'],                        'error',         '遞迴刪除路徑（包含子目錄）。'),
    _f('Rename',     'os.Rename(oldpath, newpath string) error',                 ['oldpath string','newpath string'],    'error',         '重新命名或移動。'),
    _f('Mkdir',      'os.Mkdir(name string, perm fs.FileMode) error',            ['name string','perm fs.FileMode'],     'error',         '建立目錄。'),
    _f('MkdirAll',   'os.MkdirAll(path string, perm fs.FileMode) error',         ['path string','perm fs.FileMode'],     'error',         '建立目錄（含所有父目錄）。'),
    _f('Stat',       'os.Stat(name string) (fs.FileInfo, error)',                 ['name string'],                        '(FileInfo,error)', '取得檔案資訊。'),
    _f('ReadDir',    'os.ReadDir(name string) ([]os.DirEntry, error)',            ['name string'],                        '([]DirEntry,error)', '列出目錄內容（已排序）。'),
    _f('Getenv',     'os.Getenv(key string) string',                             ['key string'],                         'string',        '取得環境變數。'),
    _f('Setenv',     'os.Setenv(key, value string) error',                       ['key string','value string'],          'error',         '設定環境變數。'),
    _f('Lookupenv',  'os.LookupEnv(key string) (string, bool)',                  ['key string'],                         '(string,bool)', '取得環境變數（區分有無設定）。'),
    _f('Environ',    'os.Environ() []string',                                     [],                                     '[]string',      '傳回所有環境變數（key=value 格式）。'),
    _f('Getwd',      'os.Getwd() (dir string, err error)',                        [],                                     '(string,error)', '取得當前工作目錄。'),
    _f('Chdir',      'os.Chdir(dir string) error',                               ['dir string'],                         'error',         '切換工作目錄。'),
    _f('Exit',       'os.Exit(code int)',                                         ['code int'],                           None,            '以指定狀態碼結束程式（不執行 defer）。'),
    _f('Getpid',     'os.Getpid() int',                                           [],                                     'int',           '傳回目前程序的 PID。'),
    _f('Hostname',   'os.Hostname() (name string, err error)',                    [],                                     '(string,error)','取得主機名稱。'),
    _f('TempDir',    'os.TempDir() string',                                       [],                                     'string',        '傳回暫存目錄路徑。'),
    _f('UserHomeDir','os.UserHomeDir() (string, error)',                          [],                                     '(string,error)','傳回目前使用者的家目錄。'),
    _v('Args',       'os.Args []string',                                          '命令列參數，Args[0] 為程式名稱。'),
    _v('Stdin',      'os.Stdin *os.File',                                         '標準輸入。'),
    _v('Stdout',     'os.Stdout *os.File',                                        '標準輸出。'),
    _v('Stderr',     'os.Stderr *os.File',                                        '標準錯誤。'),
    _v('O_RDONLY',   'os.O_RDONLY = 0',                                           '唯讀旗標。'),
    _v('O_WRONLY',   'os.O_WRONLY = 1',                                           '唯寫旗標。'),
    _v('O_RDWR',     'os.O_RDWR  = 2',                                            '讀寫旗標。'),
    _v('O_CREATE',   'os.O_CREATE = 64',                                          '若不存在則建立旗標。'),
    _v('O_TRUNC',    'os.O_TRUNC  = 512',                                         '截斷旗標。'),
    _v('O_APPEND',   'os.O_APPEND = 1024',                                        '追加旗標。'),
],

'strings': [
    _f('Contains',    'strings.Contains(s, substr string) bool',                   ['s string','substr string'],  'bool',     's 是否包含 substr。'),
    _f('ContainsAny', 'strings.ContainsAny(s, chars string) bool',                 ['s string','chars string'],   'bool',     's 是否包含 chars 中任一字元。'),
    _f('Count',       'strings.Count(s, substr string) int',                       ['s string','substr string'],  'int',      '計算 substr 出現次數（不重疊）。'),
    _f('EqualFold',   'strings.EqualFold(s, t string) bool',                       ['s string','t string'],       'bool',     '不區分大小寫比較。'),
    _f('Fields',      'strings.Fields(s string) []string',                         ['s string'],                  '[]string', '按任意空白字元分割，忽略前後空白。'),
    _f('HasPrefix',   'strings.HasPrefix(s, prefix string) bool',                  ['s string','prefix string'],  'bool',     's 是否以 prefix 開頭。'),
    _f('HasSuffix',   'strings.HasSuffix(s, suffix string) bool',                  ['s string','suffix string'],  'bool',     's 是否以 suffix 結尾。'),
    _f('Index',       'strings.Index(s, substr string) int',                       ['s string','substr string'],  'int',      'substr 首次出現的索引，未找到傳回 -1。'),
    _f('IndexRune',   'strings.IndexRune(s string, r rune) int',                   ['s string','r rune'],         'int',      'rune 首次出現的索引。'),
    _f('Join',        'strings.Join(elems []string, sep string) string',            ['elems []string','sep string'],'string',  '用 sep 連接字串切片。'),
    _f('Map',         'strings.Map(mapping func(rune) rune, s string) string',      ['mapping func(rune) rune','s string'],'string','對每個字元套用 mapping。'),
    _f('NewReader',   'strings.NewReader(s string) *strings.Reader',               ['s string'],                  '*Reader',  '從字串建立 io.Reader。'),
    _f('NewReplacer', 'strings.NewReplacer(oldnew ...string) *strings.Replacer',   ['oldnew ...string'],          '*Replacer','建立多組替換器。'),
    _f('Repeat',      'strings.Repeat(s string, count int) string',                ['s string','count int'],      'string',   '重複 s count 次。'),
    _f('Replace',     'strings.Replace(s, old, new string, n int) string',         ['s string','old string','new string','n int'],'string','替換 n 次（n=-1 全部）。'),
    _f('ReplaceAll',  'strings.ReplaceAll(s, old, new string) string',             ['s string','old string','new string'],'string','替換所有 old 為 new。'),
    _f('Split',       'strings.Split(s, sep string) []string',                     ['s string','sep string'],     '[]string', '按 sep 分割。'),
    _f('SplitN',      'strings.SplitN(s, sep string, n int) []string',             ['s string','sep string','n int'],'[]string','最多分成 n 份。'),
    _f('SplitAfter',  'strings.SplitAfter(s, sep string) []string',               ['s string','sep string'],     '[]string', '分割後保留 sep。'),
    _f('Title',       'strings.Title(s string) string',                            ['s string'],                  'string',   '每個單字首字母大寫（deprecated，用 golang.org/x/text/cases）。'),
    _f('ToLower',     'strings.ToLower(s string) string',                          ['s string'],                  'string',   '轉為小寫。'),
    _f('ToTitle',     'strings.ToTitle(s string) string',                          ['s string'],                  'string',   '轉為標題大小寫。'),
    _f('ToUpper',     'strings.ToUpper(s string) string',                          ['s string'],                  'string',   '轉為大寫。'),
    _f('Trim',        'strings.Trim(s, cutset string) string',                     ['s string','cutset string'],  'string',   '去除 cutset 中任一字元（前後）。'),
    _f('TrimFunc',    'strings.TrimFunc(s string, f func(rune) bool) string',      ['s string','f func(rune) bool'],'string', '去除符合 f 的字元（前後）。'),
    _f('TrimLeft',    'strings.TrimLeft(s, cutset string) string',                 ['s string','cutset string'],  'string',   '去除左側 cutset 字元。'),
    _f('TrimPrefix',  'strings.TrimPrefix(s, prefix string) string',               ['s string','prefix string'],  'string',   '去除前綴。'),
    _f('TrimRight',   'strings.TrimRight(s, cutset string) string',                ['s string','cutset string'],  'string',   '去除右側 cutset 字元。'),
    _f('TrimSpace',   'strings.TrimSpace(s string) string',                        ['s string'],                  'string',   '去除前後空白字元。'),
    _f('TrimSuffix',  'strings.TrimSuffix(s, suffix string) string',               ['s string','suffix string'],  'string',   '去除後綴。'),
    _t('Builder',     'type strings.Builder struct',                                '高效字串建構器（b.WriteString, b.String）。'),
],

'strconv': [
    _f('Atoi',        'strconv.Atoi(s string) (int, error)',                   ['s string'],             '(int,error)',    '字串轉 int。'),
    _f('Itoa',        'strconv.Itoa(i int) string',                            ['i int'],                'string',         'int 轉字串。'),
    _f('ParseInt',    'strconv.ParseInt(s string, base, bitSize int) (int64, error)', ['s string','base int','bitSize int'], '(int64,error)', '字串轉 int64（指定進位和位元寬度）。'),
    _f('ParseUint',   'strconv.ParseUint(s string, base, bitSize int) (uint64, error)',['s string','base int','bitSize int'],'(uint64,error)','字串轉 uint64。'),
    _f('ParseFloat',  'strconv.ParseFloat(s string, bitSize int) (float64, error)',    ['s string','bitSize int'],           '(float64,error)','字串轉 float64。'),
    _f('ParseBool',   'strconv.ParseBool(str string) (bool, error)',           ['str string'],           '(bool,error)',   '"true"/"false"/"1"/"0" 等字串轉 bool。'),
    _f('FormatInt',   'strconv.FormatInt(i int64, base int) string',           ['i int64','base int'],   'string',         'int64 轉字串（指定進位）。'),
    _f('FormatUint',  'strconv.FormatUint(i uint64, base int) string',         ['i uint64','base int'],  'string',         'uint64 轉字串。'),
    _f('FormatFloat', 'strconv.FormatFloat(f float64, fmt byte, prec, bitSize int) string', ['f float64','fmt byte','prec int','bitSize int'],'string','float64 轉字串。'),
    _f('FormatBool',  'strconv.FormatBool(b bool) string',                     ['b bool'],               'string',         'bool 轉字串。'),
    _f('AppendInt',   'strconv.AppendInt(dst []byte, i int64, base int) []byte',['dst []byte','i int64','base int'],'[]byte','追加 int64 字串到 byte slice。'),
    _f('Quote',       'strconv.Quote(s string) string',                        ['s string'],             'string',         '轉為 Go 字串字面量（帶雙引號）。'),
    _f('Unquote',     'strconv.Unquote(s string) (string, error)',             ['s string'],             '(string,error)', '解析 Go 字串字面量。'),
],

'sort': [
    _f('Slice',          'sort.Slice(x any, less func(i, j int) bool)',           ['x any','less func(i, j int) bool'],None,    '對 slice 排序（不穩定）。'),
    _f('SliceStable',    'sort.SliceStable(x any, less func(i, j int) bool)',     ['x any','less func(i, j int) bool'],None,    '穩定排序 slice。'),
    _f('SliceIsSorted',  'sort.SliceIsSorted(x any, less func(i, j int) bool) bool',['x any','less func(i, j int) bool'],'bool','檢查 slice 是否已排序。'),
    _f('Ints',           'sort.Ints(a []int)',                                    ['a []int'],             None,    '升序排序 int slice。'),
    _f('IntsAreSorted',  'sort.IntsAreSorted(a []int) bool',                     ['a []int'],             'bool',  '檢查 int slice 是否已排序。'),
    _f('Strings',        'sort.Strings(a []string)',                              ['a []string'],          None,    '升序排序字串 slice。'),
    _f('StringsAreSorted','sort.StringsAreSorted(a []string) bool',              ['a []string'],          'bool',  '檢查字串 slice 是否已排序。'),
    _f('Float64s',       'sort.Float64s(a []float64)',                            ['a []float64'],         None,    '升序排序 float64 slice。'),
    _f('Search',         'sort.Search(n int, f func(int) bool) int',             ['n int','f func(int) bool'],'int','二分搜尋：最小 i∈[0,n) 使 f(i)=true。'),
    _f('SearchInts',     'sort.SearchInts(a []int, x int) int',                  ['a []int','x int'],     'int',   '在已排序 int slice 中搜尋 x。'),
    _f('SearchStrings',  'sort.SearchStrings(a []string, x string) int',         ['a []string','x string'],'int',  '在已排序字串 slice 中搜尋 x。'),
    _t('Interface',      'type sort.Interface interface { Len() int; Less(i,j int) bool; Swap(i,j int) }', '實作此介面以使用 sort.Sort。'),
],

'math': [
    _f('Abs',    'math.Abs(x float64) float64',                   ['x float64'],            'float64', '絕對值。'),
    _f('Ceil',   'math.Ceil(x float64) float64',                  ['x float64'],            'float64', '向上取整。'),
    _f('Floor',  'math.Floor(x float64) float64',                 ['x float64'],            'float64', '向下取整。'),
    _f('Round',  'math.Round(x float64) float64',                 ['x float64'],            'float64', '四捨五入到最近整數。'),
    _f('Sqrt',   'math.Sqrt(x float64) float64',                  ['x float64'],            'float64', '平方根。'),
    _f('Cbrt',   'math.Cbrt(x float64) float64',                  ['x float64'],            'float64', '立方根。'),
    _f('Pow',    'math.Pow(x, y float64) float64',                ['x float64','y float64'],'float64', 'x 的 y 次方。'),
    _f('Pow10',  'math.Pow10(n int) float64',                     ['n int'],                'float64', '10 的 n 次方。'),
    _f('Max',    'math.Max(x, y float64) float64',                ['x float64','y float64'],'float64', '兩數最大值（NaN 傳播）。'),
    _f('Min',    'math.Min(x, y float64) float64',                ['x float64','y float64'],'float64', '兩數最小值（NaN 傳播）。'),
    _f('Log',    'math.Log(x float64) float64',                   ['x float64'],            'float64', '自然對數。'),
    _f('Log2',   'math.Log2(x float64) float64',                  ['x float64'],            'float64', '以 2 為底的對數。'),
    _f('Log10',  'math.Log10(x float64) float64',                 ['x float64'],            'float64', '以 10 為底的對數。'),
    _f('Exp',    'math.Exp(x float64) float64',                   ['x float64'],            'float64', 'e 的 x 次方。'),
    _f('Exp2',   'math.Exp2(x float64) float64',                  ['x float64'],            'float64', '2 的 x 次方。'),
    _f('Sin',    'math.Sin(x float64) float64',                   ['x float64'],            'float64', '正弦（弧度）。'),
    _f('Cos',    'math.Cos(x float64) float64',                   ['x float64'],            'float64', '餘弦（弧度）。'),
    _f('Tan',    'math.Tan(x float64) float64',                   ['x float64'],            'float64', '正切（弧度）。'),
    _f('Atan2',  'math.Atan2(y, x float64) float64',             ['y float64','x float64'],'float64', '反正切（y/x 的角度）。'),
    _f('Hypot',  'math.Hypot(p, q float64) float64',             ['p float64','q float64'],'float64', '歐幾里得距離 √(p²+q²)。'),
    _f('Mod',    'math.Mod(x, y float64) float64',               ['x float64','y float64'],'float64', '浮點取餘。'),
    _f('Trunc',  'math.Trunc(x float64) float64',                ['x float64'],            'float64', '截去小數部分。'),
    _f('IsNaN',  'math.IsNaN(f float64) bool',                    ['f float64'],            'bool',    '是否為 NaN。'),
    _f('IsInf',  'math.IsInf(f float64, sign int) bool',         ['f float64','sign int'], 'bool',    '是否為無限大。'),
    _f('Inf',    'math.Inf(sign int) float64',                    ['sign int'],             'float64', '正負無限大（sign>0 為+∞）。'),
    _f('NaN',    'math.NaN() float64',                            [],                       'float64', '傳回 NaN。'),
    _v('Pi',     'math.Pi = 3.141592653589793',                   '圓周率 π。'),
    _v('E',      'math.E  = 2.718281828459045',                   '自然對數底數 e。'),
    _v('Phi',    'math.Phi = 1.618033988749895',                  '黃金比例 φ。'),
    _v('MaxInt', 'math.MaxInt',                                    '最大 int 值。'),
    _v('MinInt', 'math.MinInt',                                    '最小 int 值。'),
    _v('MaxFloat64','math.MaxFloat64',                             '最大 float64 值。'),
],

'time': [
    _f('Now',          'time.Now() time.Time',                                             [],                      'Time',          '傳回當前本地時間。'),
    _f('Sleep',        'time.Sleep(d time.Duration)',                                       ['d Duration'],           None,            '暫停執行 d 時間。'),
    _f('Since',        'time.Since(t time.Time) time.Duration',                            ['t Time'],               'Duration',      '從 t 至今的時間差。'),
    _f('Until',        'time.Until(t time.Time) time.Duration',                            ['t Time'],               'Duration',      '從現在到 t 的時間差。'),
    _f('After',        'time.After(d time.Duration) <-chan time.Time',                     ['d Duration'],           '<-chan Time',   'd 後傳送時間到 channel。'),
    _f('AfterFunc',    'time.AfterFunc(d time.Duration, f func()) *time.Timer',            ['d Duration','f func()'],'*Timer',        'd 後在新 goroutine 執行 f。'),
    _f('NewTimer',     'time.NewTimer(d time.Duration) *time.Timer',                       ['d Duration'],           '*Timer',        '建立計時器（.C 為 channel，.Stop() 取消）。'),
    _f('NewTicker',    'time.NewTicker(d time.Duration) *time.Ticker',                     ['d Duration'],           '*Ticker',       '建立週期計時器（.C 為 channel，.Stop() 取消）。'),
    _f('Parse',        'time.Parse(layout, value string) (time.Time, error)',              ['layout string','value string'],'(Time,error)','按 layout 解析時間字串（layout 用 2006-01-02 等）。'),
    _f('ParseDuration','time.ParseDuration(s string) (time.Duration, error)',              ['s string'],             '(Duration,error)','解析時間段字串（如 "1h30m"）。'),
    _f('Date',         'time.Date(year, month, day, hour, min, sec, nsec int, loc *time.Location) time.Time', ['year int','month Month','day int','hour int','min int','sec int','nsec int','loc *Location'],'Time','建立指定時間。'),
    _f('Unix',         'time.Unix(sec int64, nsec int64) time.Time',                       ['sec int64','nsec int64'],'Time',         '從 Unix 時間戳建立 Time。'),
    _f('LoadLocation', 'time.LoadLocation(name string) (*time.Location, error)',            ['name string'],          '(*Location,error)','載入時區（如 "Asia/Taipei"）。'),
    _v('Second',       'time.Second time.Duration = 1_000_000_000',                        '1 秒。'),
    _v('Millisecond',  'time.Millisecond time.Duration = 1_000_000',                       '1 毫秒。'),
    _v('Microsecond',  'time.Microsecond time.Duration = 1_000',                           '1 微秒。'),
    _v('Nanosecond',   'time.Nanosecond time.Duration = 1',                                '1 奈秒。'),
    _v('Minute',       'time.Minute time.Duration = 60_000_000_000',                       '1 分鐘。'),
    _v('Hour',         'time.Hour time.Duration = 3_600_000_000_000',                      '1 小時。'),
    _v('UTC',          'time.UTC *time.Location',                                          'UTC 時區。'),
    _v('Local',        'time.Local *time.Location',                                        '本地時區。'),
],

'sync': [
    _t('Mutex',     'type sync.Mutex struct — Lock(), Unlock()',               '互斥鎖（零值即可使用，搭配 defer Unlock() 使用）。'),
    _t('RWMutex',   'type sync.RWMutex struct — RLock(), RUnlock(), Lock(), Unlock()', '讀寫鎖（多讀單寫）。'),
    _t('WaitGroup', 'type sync.WaitGroup struct — Add(n), Done(), Wait()',     '等待 goroutine 群組完成（零值即可使用）。'),
    _t('Once',      'type sync.Once struct — Do(f func())',                    '確保函式只被呼叫一次（執行緒安全初始化）。'),
    _t('Map',       'type sync.Map struct — Store(k,v), Load(k), Delete(k), Range(f)', '並發安全的 map（無需初始化）。'),
    _t('Cond',      'type sync.Cond struct — Wait(), Signal(), Broadcast()',   '條件變數（用 sync.NewCond(locker) 建立）。'),
    _f('NewCond',   'sync.NewCond(l sync.Locker) *sync.Cond',                 ['l Locker'],          '*Cond', '建立條件變數。'),
    _t('Pool',      'type sync.Pool struct — Get() any, Put(x any)',           '暫存物件池（減少 GC 壓力）。'),
],

'errors': [
    _f('New',    'errors.New(text string) error',             ['text string'],         'error', '建立新的 error。'),
    _f('Is',     'errors.Is(err, target error) bool',         ['err error','target error'],'bool', '檢查 err 鏈中是否含 target（支援 Unwrap）。'),
    _f('As',     'errors.As(err error, target any) bool',     ['err error','target any'],'bool', '從 err 鏈提取特定型別的 error。'),
    _f('Unwrap', 'errors.Unwrap(err error) error',            ['err error'],           'error', '取得包裝的下一層 error。'),
    _f('Join',   'errors.Join(errs ...error) error',          ['errs ...error'],       'error', '合併多個 error（Go 1.20+）。'),
],

'io': [
    _f('Copy',        'io.Copy(dst io.Writer, src io.Reader) (written int64, err error)', ['dst Writer','src Reader'],'(int64,error)', '從 src 複製到 dst。'),
    _f('CopyN',       'io.CopyN(dst io.Writer, src io.Reader, n int64) (written int64, err error)',['dst Writer','src Reader','n int64'],'(int64,error)','最多複製 n 個位元組。'),
    _f('ReadAll',     'io.ReadAll(r io.Reader) ([]byte, error)',                          ['r Reader'],            '([]byte,error)', '讀取 r 直到 EOF。'),
    _f('ReadFull',    'io.ReadFull(r io.Reader, buf []byte) (n int, err error)',          ['r Reader','buf []byte'],'(int,error)',    '確保讀滿 buf。'),
    _f('WriteString', 'io.WriteString(w io.Writer, s string) (n int, err error)',         ['w Writer','s string'], '(int,error)',    '將字串寫入 w。'),
    _f('Pipe',        'io.Pipe() (*io.PipeReader, *io.PipeWriter)',                       [],                      '(*PipeReader,*PipeWriter)', '建立同步記憶體管道。'),
    _f('MultiWriter', 'io.MultiWriter(writers ...io.Writer) io.Writer',                   ['writers ...Writer'],   'Writer',         '同時寫入多個 Writer。'),
    _f('MultiReader', 'io.MultiReader(readers ...io.Reader) io.Reader',                   ['readers ...Reader'],   'Reader',         '依序讀取多個 Reader。'),
    _f('TeeReader',   'io.TeeReader(r io.Reader, w io.Writer) io.Reader',                 ['r Reader','w Writer'], 'Reader',         '讀取時同時寫入 w（類似 tee 命令）。'),
    _f('LimitReader', 'io.LimitReader(r io.Reader, n int64) io.Reader',                   ['r Reader','n int64'],  'Reader',         '限制最多讀取 n 個位元組。'),
    _f('NopCloser',   'io.NopCloser(r io.Reader) io.ReadCloser',                          ['r Reader'],            'ReadCloser',     '包裝 Reader，提供空的 Close 方法。'),
    _f('Discard',     'io.Discard io.Writer',                                             [],                      'Writer',         '丟棄所有寫入（/dev/null）。'),
    _v('EOF',         'io.EOF = errors.New("EOF")',                                        '到達檔案結尾的標準 error。'),
    _v('ErrClosedPipe','io.ErrClosedPipe = errors.New("io: read/write on closed pipe")',   '已關閉管道的 error。'),
    _v('ErrUnexpectedEOF','io.ErrUnexpectedEOF',                                          '在讀取固定大小資料時提早遇到 EOF。'),
    _v('SeekStart',   'io.SeekStart = 0',                                                  'Seek 從檔案開頭計算。'),
    _v('SeekCurrent', 'io.SeekCurrent = 1',                                                'Seek 從目前位置計算。'),
    _v('SeekEnd',     'io.SeekEnd = 2',                                                    'Seek 從檔案結尾計算。'),
],

'bufio': [
    _f('NewScanner',  'bufio.NewScanner(r io.Reader) *bufio.Scanner',   ['r Reader'], '*Scanner', '建立逐行掃描器。Scanner.Scan() 讀下一行，Scanner.Text() 取文字。'),
    _f('NewReader',   'bufio.NewReader(rd io.Reader) *bufio.Reader',    ['rd Reader'],'*Reader',  '建立帶緩衝的讀取器（預設 4096 bytes）。'),
    _f('NewReaderSize','bufio.NewReaderSize(rd io.Reader, size int) *bufio.Reader',['rd Reader','size int'],'*Reader','建立指定緩衝大小的讀取器。'),
    _f('NewWriter',   'bufio.NewWriter(w io.Writer) *bufio.Writer',     ['w Writer'], '*Writer',  '建立帶緩衝的寫入器（記得呼叫 Flush）。'),
    _f('NewWriterSize','bufio.NewWriterSize(w io.Writer, size int) *bufio.Writer',['w Writer','size int'],'*Writer','建立指定緩衝大小的寫入器。'),
    _f('NewReadWriter','bufio.NewReadWriter(r *bufio.Reader, w *bufio.Writer) *bufio.ReadWriter',['r *Reader','w *Writer'],'*ReadWriter','讀寫緩衝合體。'),
],

'encoding/json': [
    _f('Marshal',      'json.Marshal(v any) ([]byte, error)',                    ['v any'],                  '([]byte,error)', '序列化為 JSON。struct tag `json:"name"` 控制輸出。'),
    _f('MarshalIndent','json.MarshalIndent(v any, prefix, indent string) ([]byte, error)',['v any','prefix string','indent string'],'([]byte,error)','序列化為帶縮排的 JSON。'),
    _f('Unmarshal',    'json.Unmarshal(data []byte, v any) error',              ['data []byte','v any'],    'error',          '反序列化 JSON 到 v（v 須為指針）。'),
    _f('NewEncoder',   'json.NewEncoder(w io.Writer) *json.Encoder',            ['w io.Writer'],            '*Encoder',       '建立 JSON 編碼器（Encode 方法寫入並換行）。'),
    _f('NewDecoder',   'json.NewDecoder(r io.Reader) *json.Decoder',            ['r io.Reader'],            '*Decoder',       '建立 JSON 解碼器（Decode 方法讀取一個 JSON 值）。'),
    _f('Valid',        'json.Valid(data []byte) bool',                           ['data []byte'],            'bool',           '檢查 data 是否為有效 JSON。'),
    _t('RawMessage',   'type json.RawMessage []byte',                            '原始 JSON 片段（延遲解析用）。'),
    _t('Decoder',      'type json.Decoder struct — Decode(v any) error, More() bool, Token() (Token, error)', '串流 JSON 解碼器。'),
    _t('Encoder',      'type json.Encoder struct — Encode(v any) error, SetIndent(prefix, indent string)', '串流 JSON 編碼器。'),
],

'net/http': [
    _f('Get',            'http.Get(url string) (resp *http.Response, err error)',             ['url string'],                    '(*Response,error)', '發送 HTTP GET 請求。'),
    _f('Post',           'http.Post(url, contentType string, body io.Reader) (*http.Response, error)',['url string','contentType string','body io.Reader'],'(*Response,error)','發送 HTTP POST 請求。'),
    _f('PostForm',       'http.PostForm(url string, data url.Values) (*http.Response, error)', ['url string','data url.Values'], '(*Response,error)', '以 application/x-www-form-urlencoded 格式 POST。'),
    _f('Head',           'http.Head(url string) (resp *http.Response, err error)',            ['url string'],                    '(*Response,error)', '發送 HTTP HEAD 請求。'),
    _f('HandleFunc',     'http.HandleFunc(pattern string, handler func(ResponseWriter, *Request))', ['pattern string','handler func(ResponseWriter,*Request)'],None,'在預設 ServeMux 上註冊路由。'),
    _f('Handle',         'http.Handle(pattern string, handler http.Handler)',                 ['pattern string','handler Handler'],None,               '在預設 ServeMux 上註冊 Handler。'),
    _f('ListenAndServe', 'http.ListenAndServe(addr string, handler http.Handler) error',      ['addr string','handler Handler'], 'error',             '啟動 HTTP 伺服器（nil handler 使用預設 ServeMux）。'),
    _f('ListenAndServeTLS','http.ListenAndServeTLS(addr, certFile, keyFile string, handler http.Handler) error',['addr string','certFile string','keyFile string','handler Handler'],'error','啟動 HTTPS 伺服器。'),
    _f('NewRequest',     'http.NewRequest(method, url string, body io.Reader) (*http.Request, error)',['method string','url string','body io.Reader'],'(*Request,error)','建立 HTTP 請求（可設 Header）。'),
    _f('NewServeMux',    'http.NewServeMux() *http.ServeMux',                                [],                                '*ServeMux',         '建立新的路由 Mux。'),
    _f('Error',          'http.Error(w http.ResponseWriter, error string, code int)',         ['w ResponseWriter','error string','code int'],None,'傳送 HTTP 錯誤回應。'),
    _f('Redirect',       'http.Redirect(w http.ResponseWriter, r *http.Request, url string, code int)',['w ResponseWriter','r *Request','url string','code int'],None,'重新導向。'),
    _f('NotFound',       'http.NotFound(w http.ResponseWriter, r *http.Request)',             ['w ResponseWriter','r *Request'],None,'傳送 404 回應。'),
    _f('ServeContent',   'http.ServeContent(w ResponseWriter, r *Request, name string, modtime time.Time, content io.ReadSeeker)',['w ResponseWriter','r *Request','name string','modtime Time','content io.ReadSeeker'],None,'提供靜態內容（支援範圍請求）。'),
    _f('ServeFile',      'http.ServeFile(w ResponseWriter, r *Request, name string)',        ['w ResponseWriter','r *Request','name string'],None,'提供靜態檔案。'),
    _v('StatusOK',             'http.StatusOK = 200',             'HTTP 200 OK。'),
    _v('StatusCreated',        'http.StatusCreated = 201',        'HTTP 201 Created。'),
    _v('StatusNoContent',      'http.StatusNoContent = 204',      'HTTP 204 No Content。'),
    _v('StatusBadRequest',     'http.StatusBadRequest = 400',     'HTTP 400 Bad Request。'),
    _v('StatusUnauthorized',   'http.StatusUnauthorized = 401',   'HTTP 401 Unauthorized。'),
    _v('StatusForbidden',      'http.StatusForbidden = 403',      'HTTP 403 Forbidden。'),
    _v('StatusNotFound',       'http.StatusNotFound = 404',       'HTTP 404 Not Found。'),
    _v('StatusInternalServerError','http.StatusInternalServerError = 500','HTTP 500 Internal Server Error。'),
    _v('DefaultClient',        'http.DefaultClient *http.Client',  '預設 HTTP 客戶端（30 秒逾時）。'),
    _v('DefaultServeMux',      'http.DefaultServeMux *http.ServeMux','預設路由 Mux。'),
],

'log': [
    _f('Print',   'log.Print(v ...any)',                      ['v ...any'],             None, '輸出到日誌，附時間戳。'),
    _f('Println', 'log.Println(v ...any)',                    ['v ...any'],             None, '輸出到日誌，附時間戳，末尾換行。'),
    _f('Printf',  'log.Printf(format string, v ...any)',      ['format string','v ...any'],None,'格式化輸出到日誌。'),
    _f('Fatal',   'log.Fatal(v ...any)',                      ['v ...any'],             None, '輸出後呼叫 os.Exit(1)。'),
    _f('Fatalf',  'log.Fatalf(format string, v ...any)',      ['format string','v ...any'],None,'格式化輸出後呼叫 os.Exit(1)。'),
    _f('Panic',   'log.Panic(v ...any)',                      ['v ...any'],             None, '輸出後呼叫 panic。'),
    _f('Panicf',  'log.Panicf(format string, v ...any)',      ['format string','v ...any'],None,'格式化輸出後呼叫 panic。'),
    _f('SetFlags','log.SetFlags(flag int)',                    ['flag int'],             None, '設定日誌旗標（如 log.Ldate|log.Ltime）。'),
    _f('SetPrefix','log.SetPrefix(prefix string)',             ['prefix string'],        None, '設定日誌前綴。'),
    _f('New',     'log.New(out io.Writer, prefix string, flag int) *log.Logger',['out io.Writer','prefix string','flag int'],'*Logger','建立自訂 Logger。'),
    _v('Ldate',    'log.Ldate   = 1',   '日誌旗標：顯示日期。'),
    _v('Ltime',    'log.Ltime   = 2',   '日誌旗標：顯示時間。'),
    _v('Lmsgprefix','log.Lmsgprefix = 64','日誌旗標：前綴放在訊息前。'),
],

'path/filepath': [
    _f('Join',     'filepath.Join(elem ...string) string',                  ['elem ...string'],             'string',         '連接路徑元素（使用 OS 分隔符）。'),
    _f('Abs',      'filepath.Abs(path string) (string, error)',             ['path string'],                '(string,error)', '傳回絕對路徑。'),
    _f('Dir',      'filepath.Dir(path string) string',                     ['path string'],                'string',         '傳回路徑的目錄部分。'),
    _f('Base',     'filepath.Base(path string) string',                    ['path string'],                'string',         '傳回路徑的最後元素（檔名）。'),
    _f('Ext',      'filepath.Ext(path string) string',                     ['path string'],                'string',         '傳回副檔名（含 .）。'),
    _f('Glob',     'filepath.Glob(pattern string) (matches []string, err error)',['pattern string'],       '([]string,error)','傳回符合 pattern 的路徑列表。'),
    _f('Walk',     'filepath.Walk(root string, fn fs.WalkFunc) error',     ['root string','fn fs.WalkFunc'],'error',         '遞迴遍歷目錄樹（已棄用，用 WalkDir）。'),
    _f('WalkDir',  'filepath.WalkDir(root string, fn fs.WalkDirFunc) error',['root string','fn fs.WalkDirFunc'],'error',     '遞迴遍歷目錄樹（推薦）。'),
    _f('Rel',      'filepath.Rel(basepath, targpath string) (string, error)',['basepath string','targpath string'],'(string,error)','計算 targpath 相對於 basepath 的路徑。'),
    _f('Split',    'filepath.Split(path string) (dir, file string)',       ['path string'],                '(string,string)','分割為目錄和檔名。'),
    _f('IsAbs',    'filepath.IsAbs(path string) bool',                    ['path string'],                'bool',           '是否為絕對路徑。'),
    _f('Clean',    'filepath.Clean(path string) string',                   ['path string'],                'string',         '清理路徑（去除 . 和 ..）。'),
    _f('EvalSymlinks','filepath.EvalSymlinks(path string) (string, error)',['path string'],               '(string,error)', '解析符號連結。'),
    _f('FromSlash','filepath.FromSlash(path string) string',              ['path string'],                'string',         '將 / 替換為 OS 路徑分隔符。'),
    _f('ToSlash',  'filepath.ToSlash(path string) string',                ['path string'],                'string',         '將 OS 路徑分隔符替換為 /。'),
    _f('Match',    'filepath.Match(pattern, name string) (matched bool, err error)',['pattern string','name string'],'(bool,error)','檢查 name 是否符合 shell 路徑模式。'),
],

'context': [
    _f('Background',   'context.Background() context.Context',                             [],'Context',        '根 context（永不取消，用於頂層）。'),
    _f('TODO',         'context.TODO() context.Context',                                   [],'Context',        '占位 context（待確定場景時使用）。'),
    _f('WithCancel',   'context.WithCancel(parent context.Context) (context.Context, context.CancelFunc)',['parent Context'],'(Context,CancelFunc)','可手動取消的 context（呼叫 cancel() 取消）。'),
    _f('WithTimeout',  'context.WithTimeout(parent Context, timeout time.Duration) (Context, CancelFunc)',['parent Context','timeout Duration'],'(Context,CancelFunc)','有逾時的 context。'),
    _f('WithDeadline', 'context.WithDeadline(parent Context, d time.Time) (Context, CancelFunc)',['parent Context','d Time'],'(Context,CancelFunc)','有截止時間的 context。'),
    _f('WithValue',    'context.WithValue(parent Context, key, val any) Context',          ['parent Context','key any','val any'],'Context','附帶請求範圍值的 context。'),
    _f('Cause',        'context.Cause(c context.Context) error',                           ['c Context'],'error','傳回 context 取消的原因（Go 1.20+）。'),
    _f('WithCancelCause','context.WithCancelCause(parent Context) (Context, CancelCauseFunc)',['parent Context'],'(Context,CancelCauseFunc)','可指定取消原因的 context（Go 1.20+）。'),
],

'regexp': [
    _f('Compile',       'regexp.Compile(expr string) (*regexp.Regexp, error)',             ['expr string'],  '(*Regexp,error)', '編譯正規表達式。'),
    _f('MustCompile',   'regexp.MustCompile(str string) *regexp.Regexp',                  ['str string'],   '*Regexp',         '編譯，失敗則 panic（用於初始化全域變數）。'),
    _f('CompilePOSIX',  'regexp.CompilePOSIX(expr string) (*regexp.Regexp, error)',        ['expr string'],  '(*Regexp,error)', '編譯 POSIX ERE 正規表達式（最長匹配）。'),
    _f('MustCompilePOSIX','regexp.MustCompilePOSIX(str string) *regexp.Regexp',           ['str string'],   '*Regexp',         'CompilePOSIX 的 Must 版本。'),
    _f('MatchString',   'regexp.MatchString(pattern string, s string) (matched bool, err error)',['pattern string','s string'],'(bool,error)','快速檢查字串是否符合模式。'),
    _f('QuoteMeta',     'regexp.QuoteMeta(s string) string',                              ['s string'],     'string',          '將字串中的特殊字元轉義。'),
],

'sync/atomic': [
    _f('AddInt32',    'atomic.AddInt32(addr *int32, delta int32) (new int32)',     ['addr *int32','delta int32'],  'int32',   '原子加法（int32）。'),
    _f('AddInt64',    'atomic.AddInt64(addr *int64, delta int64) (new int64)',     ['addr *int64','delta int64'],  'int64',   '原子加法（int64）。'),
    _f('LoadInt32',   'atomic.LoadInt32(addr *int32) (val int32)',                 ['addr *int32'],               'int32',   '原子讀取（int32）。'),
    _f('LoadInt64',   'atomic.LoadInt64(addr *int64) (val int64)',                 ['addr *int64'],               'int64',   '原子讀取（int64）。'),
    _f('StoreInt32',  'atomic.StoreInt32(addr *int32, val int32)',                 ['addr *int32','val int32'],   None,      '原子寫入（int32）。'),
    _f('StoreInt64',  'atomic.StoreInt64(addr *int64, val int64)',                 ['addr *int64','val int64'],   None,      '原子寫入（int64）。'),
    _f('CompareAndSwapInt64','atomic.CompareAndSwapInt64(addr *int64, old, new int64) (swapped bool)',['addr *int64','old int64','new int64'],'bool','CAS 操作（int64）。'),
    _t('Value',       'type atomic.Value struct — Store(v any), Load() any, Swap(v any) any, CompareAndSwap(old, new any) bool','原子儲存任意型別（Go 1.4+）。'),
],

}  # end GO_PACKAGES


def get_symbols_for_package(pkg_name: str, alias: str | None = None) -> list[dict]:
    """
    傳回套件的符號列表，套用 alias（若有）。
    例如：import gofmt "encoding/json" → alias='gofmt', pkg_name='encoding/json'
    """
    syms = GO_PACKAGES.get(pkg_name, [])
    display = alias or pkg_name.split('/')[-1]
    result = []
    for s in syms:
        ns = dict(s)
        ns['source'] = 'module'
        ns['module'] = display
        ns['parent'] = None
        # Update sig to use alias
        if alias and alias != display and 'sig' in ns:
            old_prefix = (pkg_name.split('/')[-1] + '.') if '.' in ns['sig'] else ''
            ns['sig'] = ns['sig'].replace(old_prefix, alias + '.', 1) if old_prefix else ns['sig']
        result.append(ns)
    return result


def parse_go_imports_from_flow(flow_nodes: list) -> dict[str, str]:
    """
    從 flow 節點列表提取 Go import 語句並傳回 {alias: pkg_name} 映射。
    """
    import re
    packages: dict[str, str] = {}
    for node in flow_nodes:
        if node.get('type') != 'import':
            continue
        text = node.get('detail', '')
        # Match: "pkg/name" or alias "pkg/name"
        for m in re.finditer(r'(?:(\w+)\s+)?"([\w/]+)"', text):
            pkg = m.group(2)
            alias = m.group(1) or pkg.split('/')[-1]
            packages[alias] = pkg
    return packages

def parse_go_imports_from_code(code: str) -> dict[str, str]:
    """
    從 Go 原始碼提取所有 import 語句，傳回 {alias: pkg_path} 字典。
    支援：
      import "fmt"
      import alias "pkg"
      import ( ... )
    """
    import re
    packages: dict[str, str] = {}
    
    # 1. import 區塊: import ( ... )
    block_m = re.search(r'import\s*\(([^)]+)\)', code, re.DOTALL)
    if block_m:
        block = block_m.group(1)
        for m in re.finditer(r'(?:(\w+)\s+)?"([\w/]+)"', block):
            pkg   = m.group(2)
            alias = m.group(1) or pkg.split('/')[-1]
            packages[alias] = pkg
    
    # 2. 單行 import: import "fmt" 或 import alias "fmt"
    for m in re.finditer(r'^import\s+(?:(\w+)\s+)?"([\w/]+)"', code, re.MULTILINE):
        pkg   = m.group(2)
        alias = m.group(1) or pkg.split('/')[-1]
        packages[alias] = pkg
    
    return packages

