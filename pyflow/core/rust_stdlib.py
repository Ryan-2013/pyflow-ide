"""
Rust 標準函式庫符號資料庫。

策略：
  - 模組級函式 (std::fs::read_to_string) → module = 'fs'
  - 型別關聯函式 (HashMap::new)          → parent = 'HashMap', kind = 'function'
  - 型別實例方法 (map.insert)            → parent = 'HashMap', kind = 'method'
  - Trait 方法                           → parent = TraitName
"""
from __future__ import annotations

def _f(name, sig, params, ret, doc, parent=None):
    return {'name':name,'kind':'function' if '::' in name or not parent else 'method',
            'sig':sig,'params':params,'ret':ret,'doc':doc,'parent':parent}

def _m(name, sig, params, ret, doc, parent):
    return {'name':name,'kind':'method','sig':sig,'params':params,'ret':ret,'doc':doc,'parent':parent}

def _t(name, sig, doc):
    return {'name':name,'kind':'class','sig':sig,'params':[],'ret':None,'doc':doc,'parent':None}

# ── 模組符號 ────────────────────────────────────────────────────

STD_FS = [
    _f('read_to_string','std::fs::read_to_string<P: AsRef<Path>>(path: P) -> io::Result<String>',
       ['path: P'],'io::Result<String>','讀取整個檔案為字串。'),
    _f('read',         'std::fs::read<P: AsRef<Path>>(path: P) -> io::Result<Vec<u8>>',
       ['path: P'],'io::Result<Vec<u8>>','讀取整個檔案為位元組序列。'),
    _f('write',        'std::fs::write<P: AsRef<Path>, C: AsRef<[u8]>>(path: P, contents: C) -> io::Result<()>',
       ['path: P','contents: C'],'io::Result<()>','將資料寫入檔案（覆蓋）。'),
    _f('copy',         'std::fs::copy<P: AsRef<Path>, Q: AsRef<Path>>(from: P, to: Q) -> io::Result<u64>',
       ['from: P','to: Q'],'io::Result<u64>','複製檔案，傳回位元組數。'),
    _f('remove_file',  'std::fs::remove_file<P: AsRef<Path>>(path: P) -> io::Result<()>',
       ['path: P'],'io::Result<()>','刪除檔案。'),
    _f('remove_dir',   'std::fs::remove_dir<P: AsRef<Path>>(path: P) -> io::Result<()>',
       ['path: P'],'io::Result<()>','刪除空目錄。'),
    _f('remove_dir_all','std::fs::remove_dir_all<P: AsRef<Path>>(path: P) -> io::Result<()>',
       ['path: P'],'io::Result<()>','遞迴刪除目錄。'),
    _f('create_dir',   'std::fs::create_dir<P: AsRef<Path>>(path: P) -> io::Result<()>',
       ['path: P'],'io::Result<()>','建立目錄。'),
    _f('create_dir_all','std::fs::create_dir_all<P: AsRef<Path>>(path: P) -> io::Result<()>',
       ['path: P'],'io::Result<()>','建立目錄（含父目錄）。'),
    _f('rename',       'std::fs::rename<P: AsRef<Path>, Q: AsRef<Path>>(from: P, to: Q) -> io::Result<()>',
       ['from: P','to: Q'],'io::Result<()>','重新命名或移動。'),
    _f('metadata',     'std::fs::metadata<P: AsRef<Path>>(path: P) -> io::Result<Metadata>',
       ['path: P'],'io::Result<Metadata>','取得檔案中繼資料。'),
    _f('symlink_metadata','std::fs::symlink_metadata<P: AsRef<Path>>(path: P) -> io::Result<Metadata>',
       ['path: P'],'io::Result<Metadata>','取得符號連結中繼資料（不跟隨連結）。'),
    _f('read_dir',     'std::fs::read_dir<P: AsRef<Path>>(path: P) -> io::Result<ReadDir>',
       ['path: P'],'io::Result<ReadDir>','讀取目錄內容。'),
    _f('canonicalize', 'std::fs::canonicalize<P: AsRef<Path>>(path: P) -> io::Result<PathBuf>',
       ['path: P'],'io::Result<PathBuf>','傳回正規化絕對路徑。'),
    _t('File',         'struct std::fs::File — open(), create(), read(), write(), flush(), seek()',
       '檔案物件。File::open 唯讀，File::create 截斷建立。'),
    _t('OpenOptions',  'struct std::fs::OpenOptions — read(b), write(b), append(b), create(b), open(path)',
       '彈性開啟檔案（可組合 read/write/append/create）。'),
    _t('DirEntry',     'struct std::fs::DirEntry — path(), file_name(), metadata(), file_type()',
       '目錄條目。'),
    _t('Metadata',     'struct std::fs::Metadata — len(), is_file(), is_dir(), is_symlink(), modified()',
       '檔案中繼資料。'),
]

STD_IO = [
    _f('stdin',    'std::io::stdin() -> Stdin',    [],'Stdin',   '取得標準輸入句柄（.lock() 取得 StdinLock）。'),
    _f('stdout',   'std::io::stdout() -> Stdout',  [],'Stdout',  '取得標準輸出句柄（.lock() 取得 StdoutLock）。'),
    _f('stderr',   'std::io::stderr() -> Stderr',  [],'Stderr',  '取得標準錯誤句柄。'),
    _f('copy',     'std::io::copy<R: Read, W: Write>(reader: &mut R, writer: &mut W) -> io::Result<u64>',
       ['reader: &mut R','writer: &mut W'],'io::Result<u64>','從 reader 複製到 writer。'),
    _f('read_to_string','std::io::read_to_string<R: Read>(reader: &mut R) -> io::Result<String>',
       ['reader: &mut R'],'io::Result<String>','讀取 reader 全部內容為字串。'),
    _t('BufReader','struct std::io::BufReader<R> — new(inner: R), read_line(&mut buf), lines()',
       '帶緩衝的讀取器（對 File 等逐行讀取必備）。'),
    _t('BufWriter','struct std::io::BufWriter<W> — new(inner: W), flush()',
       '帶緩衝的寫入器（記得呼叫 flush()）。'),
    _t('Cursor',   'struct std::io::Cursor<T> — new(inner: T), position(), seek()',
       '在記憶體 buffer 上提供 Read/Write 實作。'),
    _t('Error',    'struct std::io::Error — new(kind, error), kind(), to_string()',
       'I/O 錯誤型別。'),
    _t('Read',     'trait std::io::Read — read(&mut buf), read_to_end(&mut buf), read_to_string(&mut buf), read_exact(&mut buf)',
       '可讀取的資料源 trait。'),
    _t('Write',    'trait std::io::Write — write(&buf), write_all(&buf), flush(), write_fmt(fmt)',
       '可寫入的資料目標 trait。'),
    _t('Seek',     'trait std::io::Seek — seek(pos: SeekFrom)',
       '支援定位的 I/O trait。'),
    _t('BufRead',  'trait std::io::BufRead — read_line(&mut buf), lines(), split(byte)',
       '帶緩衝讀取的 trait（提供逐行讀取等）。'),
]

STD_PATH = [
    _f('new',     'Path::new<S: AsRef<OsStr>>(s: &S) -> &Path',             ['s: &S'],'&Path','建立 Path 引用。'),
    _f('display', 'Path::display(&self) -> Display',                         ['&self'],'Display','格式化顯示路徑（UTF-8 友好）。'),
    _m('exists',  'Path.exists(&self) -> bool',                              ['&self'],'bool','路徑是否存在。','Path'),
    _m('is_file', 'Path.is_file(&self) -> bool',                             ['&self'],'bool','是否為檔案。','Path'),
    _m('is_dir',  'Path.is_dir(&self) -> bool',                              ['&self'],'bool','是否為目錄。','Path'),
    _m('is_symlink','Path.is_symlink(&self) -> bool',                        ['&self'],'bool','是否為符號連結。','Path'),
    _m('is_absolute','Path.is_absolute(&self) -> bool',                      ['&self'],'bool','是否為絕對路徑。','Path'),
    _m('is_relative','Path.is_relative(&self) -> bool',                      ['&self'],'bool','是否為相對路徑。','Path'),
    _m('parent',  'Path.parent(&self) -> Option<&Path>',                     ['&self'],'Option<&Path>','傳回父目錄。','Path'),
    _m('file_name','Path.file_name(&self) -> Option<&OsStr>',               ['&self'],'Option<&OsStr>','傳回檔名部分。','Path'),
    _m('file_stem','Path.file_stem(&self) -> Option<&OsStr>',               ['&self'],'Option<&OsStr>','傳回不含副檔名的檔名。','Path'),
    _m('extension','Path.extension(&self) -> Option<&OsStr>',               ['&self'],'Option<&OsStr>','傳回副檔名（不含 .）。','Path'),
    _m('join',    'Path.join<P: AsRef<Path>>(&self, path: P) -> PathBuf',   ['&self','path: P'],'PathBuf','連接路徑。','Path'),
    _m('with_extension','Path.with_extension<S: AsRef<OsStr>>(&self, extension: S) -> PathBuf',['&self','extension: S'],'PathBuf','替換副檔名。','Path'),
    _m('to_str',  'Path.to_str(&self) -> Option<&str>',                     ['&self'],'Option<&str>','轉為 &str（若為有效 UTF-8）。','Path'),
    _m('to_string_lossy','Path.to_string_lossy(&self) -> Cow<str>',         ['&self'],'Cow<str>','轉為字串（非 UTF-8 字元替換為 U+FFFD）。','Path'),
    _m('components','Path.components(&self) -> Components',                  ['&self'],'Components','迭代路徑各組成部分。','Path'),
    _t('PathBuf', 'struct std::path::PathBuf — push(path), pop(), set_extension(ext), set_file_name(name)',
       '擁有所有權的路徑緩衝（相當於 String 對應 str）。'),
]

STD_COLLECTIONS = [
    # HashMap
    _f('new',         'HashMap::new() -> HashMap<K, V>',                                      [],'HashMap<K,V>','建立空 HashMap。','HashMap'),
    _f('with_capacity','HashMap::with_capacity(capacity: usize) -> HashMap<K, V>',           ['capacity: usize'],'HashMap<K,V>','建立指定初始容量的 HashMap。','HashMap'),
    _m('insert',      'HashMap.insert(&mut self, k: K, v: V) -> Option<V>',                  ['&mut self','k: K','v: V'],'Option<V>','插入鍵值對，傳回舊值。','HashMap'),
    _m('get',         'HashMap.get<Q>(&self, k: &Q) -> Option<&V>',                          ['&self','k: &Q'],'Option<&V>','取得值的共享引用。','HashMap'),
    _m('get_mut',     'HashMap.get_mut<Q>(&mut self, k: &Q) -> Option<&mut V>',              ['&mut self','k: &Q'],'Option<&mut V>','取得值的可變引用。','HashMap'),
    _m('remove',      'HashMap.remove<Q>(&mut self, k: &Q) -> Option<V>',                    ['&mut self','k: &Q'],'Option<V>','移除並傳回值。','HashMap'),
    _m('contains_key','HashMap.contains_key<Q>(&self, k: &Q) -> bool',                       ['&self','k: &Q'],'bool','檢查 key 是否存在。','HashMap'),
    _m('entry',       'HashMap.entry(&mut self, key: K) -> Entry<K, V>',                     ['&mut self','key: K'],'Entry<K,V>','取得條目（可鏈接 .or_insert()）。','HashMap'),
    _m('len',         'HashMap.len(&self) -> usize',                                          ['&self'],'usize','元素數量。','HashMap'),
    _m('is_empty',    'HashMap.is_empty(&self) -> bool',                                      ['&self'],'bool','是否為空。','HashMap'),
    _m('iter',        'HashMap.iter(&self) -> Iter<K, V>',                                   ['&self'],'Iter<K,V>','迭代 (&K, &V) 對。','HashMap'),
    _m('iter_mut',    'HashMap.iter_mut(&mut self) -> IterMut<K, V>',                        ['&mut self'],'IterMut<K,V>','迭代 (&K, &mut V) 對。','HashMap'),
    _m('keys',        'HashMap.keys(&self) -> Keys<K, V>',                                   ['&self'],'Keys<K,V>','迭代所有鍵。','HashMap'),
    _m('values',      'HashMap.values(&self) -> Values<K, V>',                               ['&self'],'Values<K,V>','迭代所有值。','HashMap'),
    _m('values_mut',  'HashMap.values_mut(&mut self) -> ValuesMut<K, V>',                    ['&mut self'],'ValuesMut<K,V>','可變迭代所有值。','HashMap'),
    _m('clear',       'HashMap.clear(&mut self)',                                              ['&mut self'],None,'清空所有元素。','HashMap'),
    _m('retain',      'HashMap.retain<F: FnMut(&K, &mut V) -> bool>(&mut self, f: F)',        ['&mut self','f: F'],None,'保留符合條件的元素。','HashMap'),
    _m('extend',      'HashMap.extend<I: IntoIterator<Item=(K,V)>>(&mut self, iter: I)',      ['&mut self','iter: I'],None,'從迭代器批量插入。','HashMap'),
    # Vec
    _f('new',         'Vec::new() -> Vec<T>',                                                 [],'Vec<T>','建立空 Vec。','Vec'),
    _f('with_capacity','Vec::with_capacity(capacity: usize) -> Vec<T>',                      ['capacity: usize'],'Vec<T>','建立指定容量的 Vec。','Vec'),
    _m('push',        'Vec.push(&mut self, value: T)',                                        ['&mut self','value: T'],None,'在末尾追加元素。','Vec'),
    _m('pop',         'Vec.pop(&mut self) -> Option<T>',                                     ['&mut self'],'Option<T>','移除並傳回最後元素。','Vec'),
    _m('len',         'Vec.len(&self) -> usize',                                              ['&self'],'usize','元素數量。','Vec'),
    _m('is_empty',    'Vec.is_empty(&self) -> bool',                                         ['&self'],'bool','是否為空。','Vec'),
    _m('get',         'Vec.get(&self, index: usize) -> Option<&T>',                          ['&self','index: usize'],'Option<&T>','安全取得元素（越界傳回 None）。','Vec'),
    _m('iter',        'Vec.iter(&self) -> Iter<T>',                                          ['&self'],'Iter<T>','迭代 &T。','Vec'),
    _m('iter_mut',    'Vec.iter_mut(&mut self) -> IterMut<T>',                               ['&mut self'],'IterMut<T>','迭代 &mut T。','Vec'),
    _m('contains',    'Vec.contains(&self, x: &T) -> bool',                                  ['&self','x: &T'],'bool','是否包含 x。','Vec'),
    _m('sort',        'Vec.sort(&mut self) where T: Ord',                                    ['&mut self'],None,'升序排序（穩定）。','Vec'),
    _m('sort_by',     'Vec.sort_by<F: FnMut(&T, &T) -> Ordering>(&mut self, compare: F)',    ['&mut self','compare: F'],None,'自訂比較排序。','Vec'),
    _m('sort_by_key', 'Vec.sort_by_key<K, F: FnMut(&T) -> K>(&mut self, f: F)',              ['&mut self','f: F'],None,'按鍵函式排序。','Vec'),
    _m('dedup',       'Vec.dedup(&mut self) where T: PartialEq',                             ['&mut self'],None,'移除相鄰重複元素。','Vec'),
    _m('retain',      'Vec.retain<F: FnMut(&T) -> bool>(&mut self, f: F)',                   ['&mut self','f: F'],None,'保留符合條件的元素。','Vec'),
    _m('extend',      'Vec.extend<I: IntoIterator<Item=T>>(&mut self, iter: I)',              ['&mut self','iter: I'],None,'追加迭代器元素。','Vec'),
    _m('truncate',    'Vec.truncate(&mut self, len: usize)',                                  ['&mut self','len: usize'],None,'截斷到 len 個元素。','Vec'),
    _m('clear',       'Vec.clear(&mut self)',                                                  ['&mut self'],None,'清空所有元素。','Vec'),
    _m('capacity',    'Vec.capacity(&self) -> usize',                                         ['&self'],'usize','目前容量。','Vec'),
    _m('reserve',     'Vec.reserve(&mut self, additional: usize)',                            ['&mut self','additional: usize'],None,'預留額外容量。','Vec'),
    _m('remove',      'Vec.remove(&mut self, index: usize) -> T',                            ['&mut self','index: usize'],'T','移除指定索引的元素（可能較慢）。','Vec'),
    _m('insert',      'Vec.insert(&mut self, index: usize, element: T)',                     ['&mut self','index: usize','element: T'],None,'在指定位置插入元素。','Vec'),
    _m('swap',        'Vec.swap(&mut self, a: usize, b: usize)',                              ['&mut self','a: usize','b: usize'],None,'交換兩個索引的元素。','Vec'),
    _m('first',       'Vec.first(&self) -> Option<&T>',                                      ['&self'],'Option<&T>','取得第一個元素。','Vec'),
    _m('last',        'Vec.last(&self) -> Option<&T>',                                       ['&self'],'Option<&T>','取得最後一個元素。','Vec'),
    _m('windows',     'Vec.windows(&self, size: usize) -> Windows<T>',                       ['&self','size: usize'],'Windows<T>','滑動視窗迭代器。','Vec'),
    _m('chunks',      'Vec.chunks(&self, chunk_size: usize) -> Chunks<T>',                   ['&self','chunk_size: usize'],'Chunks<T>','分塊迭代器。','Vec'),
    # String
    _f('new',         'String::new() -> String',                                              [],'String','建立空 String。','String'),
    _f('from',        'String::from(s: &str) -> String',                                     ['s: &str'],'String','從 &str 建立 String。','String'),
    _f('with_capacity','String::with_capacity(capacity: usize) -> String',                   ['capacity: usize'],'String','建立指定容量的 String。','String'),
    _m('push',        'String.push(&mut self, ch: char)',                                     ['&mut self','ch: char'],None,'追加字元。','String'),
    _m('push_str',    'String.push_str(&mut self, string: &str)',                             ['&mut self','string: &str'],None,'追加字串切片。','String'),
    _m('len',         'String.len(&self) -> usize',                                           ['&self'],'usize','位元組長度。','String'),
    _m('is_empty',    'String.is_empty(&self) -> bool',                                      ['&self'],'bool','是否為空。','String'),
    _m('contains',    'String.contains<P: Pattern>(&self, pat: P) -> bool',                  ['&self','pat: P'],'bool','是否包含模式。','String'),
    _m('starts_with', 'String.starts_with<P: Pattern>(&self, pat: P) -> bool',               ['&self','pat: P'],'bool','是否以 pat 開頭。','String'),
    _m('ends_with',   'String.ends_with<P: Pattern>(&self, pat: P) -> bool',                 ['&self','pat: P'],'bool','是否以 pat 結尾。','String'),
    _m('replace',     'String.replace<P: Pattern>(&self, from: P, to: &str) -> String',      ['&self','from: P','to: &str'],'String','替換所有匹配。','String'),
    _m('split',       'String.split<P: Pattern>(&self, pat: P) -> Split<P>',                 ['&self','pat: P'],'Split<P>','按模式分割。','String'),
    _m('trim',        'String.trim(&self) -> &str',                                           ['&self'],'&str','去除前後空白。','String'),
    _m('trim_start',  'String.trim_start(&self) -> &str',                                    ['&self'],'&str','去除前置空白。','String'),
    _m('trim_end',    'String.trim_end(&self) -> &str',                                      ['&self'],'&str','去除後置空白。','String'),
    _m('to_lowercase','String.to_lowercase(&self) -> String',                                ['&self'],'String','轉小寫。','String'),
    _m('to_uppercase','String.to_uppercase(&self) -> String',                                ['&self'],'String','轉大寫。','String'),
    _m('parse',       'String.parse<F: FromStr>(&self) -> Result<F, F::Err>',                ['&self'],'Result<F,Err>','解析為目標型別（配合型別標注使用）。','String'),
    _m('chars',       'String.chars(&self) -> Chars',                                         ['&self'],'Chars','迭代 Unicode 字元。','String'),
    _m('bytes',       'String.bytes(&self) -> Bytes',                                         ['&self'],'Bytes','迭代位元組。','String'),
    _m('lines',       'String.lines(&self) -> Lines',                                         ['&self'],'Lines','迭代各行。','String'),
    _m('as_str',      'String.as_str(&self) -> &str',                                        ['&self'],'&str','取得 &str 切片。','String'),
    _m('clear',       'String.clear(&mut self)',                                               ['&mut self'],None,'清空字串。','String'),
]

STD_SYNC = [
    _f('new',    'Arc::new(data: T) -> Arc<T>',                          ['data: T'],    'Arc<T>',   '建立原子引用計數智慧指針（執行緒安全）。','Arc'),
    _m('clone',  'Arc.clone(&self) -> Arc<T>',                           ['&self'],      'Arc<T>',   '增加引用計數並傳回新指針。','Arc'),
    _m('strong_count','Arc.strong_count(this: &Arc<T>) -> usize',        ['this: &Arc<T>'],'usize',  '目前強引用計數。','Arc'),
    _m('downgrade','Arc.downgrade(this: &Arc<T>) -> Weak<T>',            ['this: &Arc<T>'],'Weak<T>','建立弱引用。','Arc'),
    _f('new',    'Mutex::new(t: T) -> Mutex<T>',                         ['t: T'],       'Mutex<T>', '建立互斥鎖。','Mutex'),
    _m('lock',   'Mutex.lock(&self) -> LockResult<MutexGuard<T>>',       ['&self'],      'LockResult<MutexGuard<T>>','取得鎖（阻塞直到取得，guard 離開範圍自動解鎖）。','Mutex'),
    _m('try_lock','Mutex.try_lock(&self) -> TryLockResult<MutexGuard<T>>',['&self'],     'TryLockResult','嘗試取得鎖（非阻塞）。','Mutex'),
    _f('new',    'RwLock::new(t: T) -> RwLock<T>',                       ['t: T'],       'RwLock<T>','建立讀寫鎖。','RwLock'),
    _m('read',   'RwLock.read(&self) -> LockResult<RwLockReadGuard<T>>', ['&self'],      'LockResult<RwLockReadGuard<T>>','取得共享讀鎖。','RwLock'),
    _m('write',  'RwLock.write(&self) -> LockResult<RwLockWriteGuard<T>>',['&self'],     'LockResult<RwLockWriteGuard<T>>','取得獨佔寫鎖。','RwLock'),
    _f('new',    'Rc::new(value: T) -> Rc<T>',                           ['value: T'],   'Rc<T>',    '建立引用計數指針（非執行緒安全）。','Rc'),
    _m('clone',  'Rc.clone(&self) -> Rc<T>',                             ['&self'],      'Rc<T>',    '增加引用計數。','Rc'),
    _m('strong_count','Rc.strong_count(this: &Rc<T>) -> usize',          ['this: &Rc<T>'],'usize',   '目前強引用計數。','Rc'),
    _m('downgrade','Rc.downgrade(this: &Rc<T>) -> Weak<T>',              ['this: &Rc<T>'],'Weak<T>', '建立弱引用。','Rc'),
    _t('OnceLock','struct std::sync::OnceLock<T> — get(), set(value), get_or_init(f)',
       '可安全初始化一次的 cell（執行緒安全）。'),
    _t('Barrier','struct std::sync::Barrier — new(n), wait() -> BarrierWaitResult',
       '同步 n 個執行緒到同一個 checkpoint。'),
]

STD_THREAD = [
    _f('spawn',    'std::thread::spawn<F, T>(f: F) -> JoinHandle<T>',      ['f: F'],'JoinHandle<T>','生成新執行緒。返回 JoinHandle 可呼叫 .join()。'),
    _f('sleep',    'std::thread::sleep(dur: Duration)',                      ['dur: Duration'],None,'暫停目前執行緒。'),
    _f('current',  'std::thread::current() -> Thread',                      [],'Thread','取得目前執行緒句柄。'),
    _f('yield_now','std::thread::yield_now()',                               [],None,'讓出執行權（給排程器）。'),
    _f('park',     'std::thread::park()',                                    [],None,'暫停目前執行緒直到被 unpark。'),
    _f('park_timeout','std::thread::park_timeout(dur: Duration)',            ['dur: Duration'],None,'暫停指定時間。'),
    _f('available_parallelism','std::thread::available_parallelism() -> io::Result<NonZeroUsize>',
       [],'io::Result<NonZeroUsize>','傳回可用的並行度（核心數）。'),
    _f('scope',    'std::thread::scope<\'env, F, T>(f: F) -> T',            ['f: F'],'T','Scoped thread（可借用本地資料）。'),
    _t('JoinHandle','struct std::thread::JoinHandle<T> — join() -> thread::Result<T>',
       '執行緒句柄，.join() 等待完成並取得結果。'),
    _t('Builder',  'struct std::thread::Builder — name(name), stack_size(size), spawn(f)',
       '執行緒建構器（可設定名稱和堆疊大小）。'),
]

STD_ENV = [
    _f('args',        'std::env::args() -> Args',                           [],'Args',             '命令列參數迭代器（UTF-8）。'),
    _f('args_os',     'std::env::args_os() -> ArgsOs',                      [],'ArgsOs',           '命令列參數迭代器（OsString）。'),
    _f('var',         'std::env::var<K: AsRef<OsStr>>(key: K) -> Result<String, VarError>',['key: K'],'Result<String,VarError>','取得環境變數（字串）。'),
    _f('var_os',      'std::env::var_os<K: AsRef<OsStr>>(key: K) -> Option<OsString>',    ['key: K'],'Option<OsString>','取得環境變數（OsString）。'),
    _f('set_var',     'unsafe std::env::set_var<K, V>(key: K, value: V)',                  ['key: K','value: V'],None,'設定環境變數（unsafe，多執行緒慎用）。'),
    _f('remove_var',  'unsafe std::env::remove_var<K>(key: K)',                            ['key: K'],None,'移除環境變數（unsafe）。'),
    _f('vars',        'std::env::vars() -> Vars',                           [],'Vars',             '所有環境變數迭代器（(String, String)）。'),
    _f('current_dir', 'std::env::current_dir() -> io::Result<PathBuf>',    [],'io::Result<PathBuf>','取得當前工作目錄。'),
    _f('set_current_dir','std::env::set_current_dir<P: AsRef<Path>>(path: P) -> io::Result<()>',['path: P'],'io::Result<()>','設定當前工作目錄。'),
    _f('current_exe', 'std::env::current_exe() -> io::Result<PathBuf>',    [],'io::Result<PathBuf>','取得當前可執行檔路徑。'),
    _f('home_dir',    'std::env::home_dir() -> Option<PathBuf>',            [],'Option<PathBuf>','取得家目錄（已棄用，請用 dirs crate）。'),
    _f('temp_dir',    'std::env::temp_dir() -> PathBuf',                    [],'PathBuf',          '取得暫存目錄。'),
]

# Option methods (universal)
OPTION_METHODS = [
    _m('is_some',     'Option.is_some(&self) -> bool',                               ['&self'],'bool','是否為 Some。','Option'),
    _m('is_none',     'Option.is_none(&self) -> bool',                               ['&self'],'bool','是否為 None。','Option'),
    _m('unwrap',      'Option.unwrap(self) -> T',                                    ['self'],'T','取得 Some 的值，None 則 panic。','Option'),
    _m('expect',      'Option.expect(self, msg: &str) -> T',                         ['self','msg: &str'],'T','取得 Some 的值，None 則 panic 並顯示 msg。','Option'),
    _m('unwrap_or',   'Option.unwrap_or(self, default: T) -> T',                     ['self','default: T'],'T','取得 Some 的值，或傳回 default。','Option'),
    _m('unwrap_or_else','Option.unwrap_or_else<F: FnOnce() -> T>(self, f: F) -> T',  ['self','f: F'],'T','取得 Some 的值，或執行 f 的結果。','Option'),
    _m('unwrap_or_default','Option.unwrap_or_default(self) -> T where T: Default',  ['self'],'T','取得 Some 的值，或 T::default()。','Option'),
    _m('map',         'Option.map<U, F: FnOnce(T) -> U>(self, f: F) -> Option<U>',  ['self','f: F'],'Option<U>','Some(x) → Some(f(x))，None → None。','Option'),
    _m('map_or',      'Option.map_or<U, F: FnOnce(T) -> U>(self, default: U, f: F) -> U',['self','default: U','f: F'],'U','map 的帶預設值版本。','Option'),
    _m('and_then',    'Option.and_then<U, F: FnOnce(T) -> Option<U>>(self, f: F) -> Option<U>',['self','f: F'],'Option<U>','Some(x) → f(x)（flatMap）。','Option'),
    _m('or',          'Option.or(self, optb: Option<T>) -> Option<T>',               ['self','optb: Option<T>'],'Option<T>','self 或 optb。','Option'),
    _m('or_else',     'Option.or_else<F: FnOnce() -> Option<T>>(self, f: F) -> Option<T>',['self','f: F'],'Option<T>','self 或 f() 的結果。','Option'),
    _m('filter',      'Option.filter<P: FnOnce(&T) -> bool>(self, predicate: P) -> Option<T>',['self','predicate: P'],'Option<T>','過濾 Some(x)（不滿足則轉 None）。','Option'),
    _m('ok_or',       'Option.ok_or<E>(self, err: E) -> Result<T, E>',              ['self','err: E'],'Result<T,E>','轉為 Result（None → Err(err)）。','Option'),
    _m('ok_or_else',  'Option.ok_or_else<E, F: FnOnce() -> E>(self, err: F) -> Result<T, E>',['self','err: F'],'Result<T,E>','轉為 Result（None → Err(f())）。','Option'),
    _m('flatten',     'Option.flatten(self) -> Option<T> where T: Option<T>',       ['self'],'Option<T>','Option<Option<T>> → Option<T>。','Option'),
    _m('as_ref',      'Option.as_ref(&self) -> Option<&T>',                         ['&self'],'Option<&T>','借用內部值。','Option'),
    _m('take',        'Option.take(&mut self) -> Option<T>',                         ['&mut self'],'Option<T>','取出值並置為 None。','Option'),
    _m('replace',     'Option.replace(&mut self, value: T) -> Option<T>',           ['&mut self','value: T'],'Option<T>','替換值並傳回舊值。','Option'),
    _m('zip',         'Option.zip<U>(self, other: Option<U>) -> Option<(T, U)>',    ['self','other: Option<U>'],'Option<(T,U)>','合併兩個 Option。','Option'),
    _m('unzip',       'Option.unzip(self) -> (Option<A>, Option<B>) where T: (A, B)',['self'],'(Option<A>,Option<B>)','拆開 Option<(A, B)>。','Option'),
    _m('cloned',      'Option.cloned(&self) -> Option<T> where T: Clone',           ['&self'],'Option<T>','複製內部值。','Option'),
    _m('copied',      'Option.copied(&self) -> Option<T> where T: Copy',            ['&self'],'Option<T>','複製內部值（Copy）。','Option'),
]

RESULT_METHODS = [
    _m('is_ok',       'Result.is_ok(&self) -> bool',                                ['&self'],'bool','是否為 Ok。','Result'),
    _m('is_err',      'Result.is_err(&self) -> bool',                               ['&self'],'bool','是否為 Err。','Result'),
    _m('ok',          'Result.ok(self) -> Option<T>',                               ['self'],'Option<T>','轉為 Option（Err 丟棄）。','Result'),
    _m('err',         'Result.err(self) -> Option<E>',                              ['self'],'Option<E>','取得 Err 為 Option。','Result'),
    _m('unwrap',      'Result.unwrap(self) -> T',                                   ['self'],'T','取得 Ok 值，Err 則 panic。','Result'),
    _m('expect',      'Result.expect(self, msg: &str) -> T',                        ['self','msg: &str'],'T','取得 Ok 值，Err 則 panic 並顯示 msg。','Result'),
    _m('unwrap_err',  'Result.unwrap_err(self) -> E',                               ['self'],'E','取得 Err 值，Ok 則 panic。','Result'),
    _m('unwrap_or',   'Result.unwrap_or(self, default: T) -> T',                   ['self','default: T'],'T','Ok 值或 default。','Result'),
    _m('unwrap_or_else','Result.unwrap_or_else<F: FnOnce(E) -> T>(self, op: F) -> T',['self','op: F'],'T','Ok 值或 op(err)。','Result'),
    _m('map',         'Result.map<U, F: FnOnce(T) -> U>(self, op: F) -> Result<U, E>',['self','op: F'],'Result<U,E>','Ok(x) → Ok(f(x))。','Result'),
    _m('map_err',     'Result.map_err<F, O: FnOnce(E) -> F>(self, op: O) -> Result<T, F>',['self','op: O'],'Result<T,F>','轉換 Err。','Result'),
    _m('and_then',    'Result.and_then<U, F: FnOnce(T) -> Result<U, E>>(self, op: F) -> Result<U, E>',['self','op: F'],'Result<U,E>','Ok(x) → f(x)。','Result'),
    _m('or_else',     'Result.or_else<F, O: FnOnce(E) -> Result<T, F>>(self, op: O) -> Result<T, F>',['self','op: O'],'Result<T,F>','Err(e) → f(e)。','Result'),
    _m('and',         'Result.and<U>(self, res: Result<U, E>) -> Result<U, E>',    ['self','res: Result<U,E>'],'Result<U,E>','Ok 則傳回 res。','Result'),
    _m('or',          'Result.or<F>(self, res: Result<T, F>) -> Result<T, F>',     ['self','res: Result<T,F>'],'Result<T,F>','Err 則傳回 res。','Result'),
    _m('as_ref',      'Result.as_ref(&self) -> Result<&T, &E>',                    ['&self'],'Result<&T,&E>','借用內部值。','Result'),
    _m('cloned',      'Result.cloned(&self) -> Result<T, E> where T: Clone',       ['&self'],'Result<T,E>','複製 Ok 值。','Result'),
    _m('flatten',     'Result.flatten(self) -> Result<T, E> where T: Result<T, E>',['self'],'Result<T,E>','Result<Result<T, E>, E> → Result<T, E>。','Result'),
    _m('transpose',   'Result.transpose(self) -> Option<Result<T, E>>',            ['self'],'Option<Result<T,E>>','Result<Option<T>, E> → Option<Result<T, E>>。','Result'),
    _m('inspect',     'Result.inspect<F: FnOnce(&T)>(self, f: F) -> Self',         ['self','f: F'],'Self','對 Ok 值執行副作用，傳回自身。','Result'),
    _m('inspect_err', 'Result.inspect_err<F: FnOnce(&E)>(self, f: F) -> Self',     ['self','f: F'],'Self','對 Err 值執行副作用，傳回自身。','Result'),
]

# ── 模組到符號的映射表 ─────────────────────────────────────────

RUST_MODULES: dict[str, list[dict]] = {
    'std::fs':          STD_FS,
    'fs':               STD_FS,
    'std::io':          STD_IO,
    'io':               STD_IO,
    'std::path':        STD_PATH,
    'path':             STD_PATH,
    'std::collections': STD_COLLECTIONS,
    'collections':      STD_COLLECTIONS,
    'std::sync':        STD_SYNC,
    'sync':             STD_SYNC,
    'std::thread':      STD_THREAD,
    'thread':           STD_THREAD,
    'std::env':         STD_ENV,
    'env':              STD_ENV,
    'Option':           OPTION_METHODS,
    'Result':           RESULT_METHODS,
}


def get_symbols_for_use(use_stmt: str) -> list[dict]:
    """
    解析 Rust use 語句，傳回相應的符號列表。
    例如：
      'use std::fs'                → std::fs 所有函式
      'use std::collections::HashMap' → HashMap 所有方法
      'use std::io::{Read, Write}'    → Read + Write trait
    """
    import re
    results: list[dict] = []
    
    # 提取 use 路徑（去掉 pub / pub(crate) 前綴）
    m = re.match(r'^(?:pub\s+(?:\([^)]+\)\s+)?)?use\s+(.*?)\s*;?\s*$', use_stmt)
    if not m:
        return results
    
    path = m.group(1).strip()
    
    # 處理大括號：use std::{fs, io}
    brace_m = re.match(r'^([\w:]+)::\{(.+)\}$', path)
    if brace_m:
        base, items = brace_m.group(1), brace_m.group(2)
        for item in items.split(','):
            item = item.strip()
            sub_path = f'{base}::{item}'
            results.extend(get_symbols_for_use(f'use {sub_path};'))
        return results
    
    # 提取 as 別名
    as_m = re.match(r'^(.+?)\s+as\s+(\w+)$', path)
    alias = None
    if as_m:
        path, alias = as_m.group(1).strip(), as_m.group(2)
    
    # 直接查表
    last = path.split('::')[-1]
    
    # 嘗試完整路徑、最後段、alias
    for key in [path, last, alias]:
        if key and key in RUST_MODULES:
            syms = RUST_MODULES[key]
            for s in syms:
                ns = dict(s)
                ns['source'] = 'module'
                if alias:
                    ns['module'] = alias
                results.append(ns)
            return results  # found
    
    # 嘗試父路徑（如 std::collections → collections）
    parts = path.split('::')
    for i in range(len(parts)-1, 0, -1):
        sub = '::'.join(parts[:i])
        if sub in RUST_MODULES:
            parent_sym = last  # the imported name
            # filter: only symbols matching this name
            matching = [s for s in RUST_MODULES[sub] if s.get('name') == parent_sym or s.get('parent') == parent_sym]
            for s in matching:
                ns = dict(s)
                ns['source'] = 'module'
                if alias:
                    ns['module'] = alias
                results.append(ns)
            break
    
    return results
