# 阶段07修订版：五栋建筑的外观依据与近似边界

复核日期：2026-10-24（Asia/Singapore）。本记录只使用已经下载的资料和实际查看的参考照片，不改写原始资料。官网文字、百科叙述、照片观察、源GIS属性与建模推断分开使用；资料不是同一天的2026城市快照。

## 来源与可确认的组织

| 对象 | 可确认的外观或组织 | 尺寸与需要保留的近似 |
|---|---|---|
| Alexandria Hotel | LA Conservancy确认1906原楼、1911增建，pressed brick与terra cotta的Beaux-Arts外观；2008照片可见浅黄砖面、不同宽度窗组、窗台/窗楣、顶层下的连续饰带、出挑屋檐与侧面消防梯。百科资料明确原楼8层、后部增建12层。 | 8/12层是文字依据；旧GIS统一17层不是已核实层数。源高度51.5m来自尚未独立核验的导入属性，不能用来证明每一片楼面的高度。34.6m原楼高度、后楼在现有足迹内的分界、窗距和每层高度均为推断。不能将矩形或分位数切割线称为1911增建的实测边界。 |
| Broadway–Spring Arcade | 两座12层临街塔楼和中间3层购物拱廊；街区贯通Broadway与Spring Street。照片中大拱上部有玻璃，拱下为独立的底层店面/通道带；细柱、连续花饰带、薄石色框与上部规则窗格是识别特征。2022参考支持屋顶保留无线电钢塔。 | 百科引述内部arcade为86×26英尺（26.2×7.9m）；这是二级资料中的室内通道尺寸，不是整个跨街区建筑群长宽，也不是现场测量。塔楼与中段24m切割、中央12.3m高、8m宽/11m高大拱和17m钢塔都须标推断。资料支持中央玻璃天窗、顶层Ionic柱廊，但没有完整屋顶平面和背面尺寸。 |
| Los Angeles Times / Kaufmann Building | Conservancy确认1935年建筑的Art Deco组织；2014照片清楚显示粉红/红色石材入口、深黑色基座、深凹门斗、垂直白色立面线、入口台阶与装饰浮雕。1935年主楼、1948年10层Crawford Addition和1973年6层Pereira翼是不同部分，不能混为主楼的统一层数。 | 没有已取得的测量图支持任意中心塔楼的位置、13m半径、26.5m裙房高度或入口2.4×3.5m。旧源报告42.7m不是本次独立核验的官方总高。源GIS start_date=1934可保留为原属性，1935是资料中的启用年份，不应互相覆盖。参考照片只覆盖入口及局部低角度墙面，完整顶部与背面仍不充分。 |
| Los Angeles County Hall of Records | Conservancy确认1962年、T形体量、南侧长铝百叶、陶瓷屏、屋顶餐厅外的细长支架，以及曾用于档案的无窗翼。百科明确北侧办公翼有双层高窗，南侧原档案翼采用8英尺层间隔；13/15层存在露台。官网明确陶屏为8层高。已选照片分别是夜景办公立面和历史局部后立面。 | 不应在整座T形外墙均匀排17层同尺度窗。北办公翼可采用约8组双层高节奏作为近似；无窗档案翼、百叶与陶屏应分区。8层高不等于已知26m：屏高、孔型、尺寸、偏移和现存朝向仍推断。陶屏不是规则细柱阵列的实测复刻。南向应按实际地理方位/翼部关系核对，不能只套用所有建筑共同的“正面”向量。 |
| Los Angeles Theatre | LA Conservancy明确1931年、Renaissance Revival、外立面升至5层，巨大柱、装饰檐部、花饰/人物与藤蔓是识别特征；2006照片可见柱槽、上部大拱形凹龛、水平招牌/雨棚及竖向LOS ANGELES招牌。 | 大拱是雨棚上方的立面凹龛/装饰组织，不应被解释为从地面贯通13m高的普通门洞。底层入口和上部大拱需分开建模。源整体building:levels=3、局部分部levels=6与官网5层立面并非同一种高度定义。21m、9m拱宽、13.2m拱顶、20m雨棚宽和各雕饰尺寸都没有本次取得的测量依据，须保留近似标签。 |

## 本次实际查看的照片及范围

以下文件的作者、具体许可、拍摄日期描述、下载时间、原始页面、SHA保留在`data/processed/stage07/research_registry.json`及`source_registry.json`。照片没有直接用作城市纹理。

- Alexandria：`data/raw/stage07/research/alexandria_hotel/reference_2.jpg`，2008-07-26，CC BY-SA 3.0。主要支持转角外立面，不证明1911后楼的完整分界、背面和高度。
- Spring Arcade：`spring_arcade/reference_2.jpg`，2008-07，CC BY-SA 3.0，临街入口细节；`reference_1.jpg`，2022-10-22，CC BY-SA 4.0，屋顶无线电塔及邻域。旧店招、车辆与临时广告不作为2026实况复制。
- Times：`la_times/reference_1.jpg`、`reference_3.jpg`、`reference_4.jpg`，2014-04-30，CC BY-SA 3.0；`reference_2.jpg`为CC BY 2.0，拍摄时间未知。局部入口和仰视资料不能证明整栋体量。
- Hall of Records：`hall_records/supplement_1.jpg`（CC BY 3.0）与`supplement_2.jpg`（CC BY-SA 3.0），拍摄年份未知。第二张是局部历史后立面，不能描述为近期现况。未选的1956城市照片、Hall of Justice、City Hall等不同主体不可回用于此楼。
- Theatre：`la_theatre/reference_1.jpg`，2006-03-10，CC BY-SA 2.0。另一张Los Angeles Theatre Center照片是不同场馆，不能用于该楼。

## 文字资料定位

- Conservancy的本地文字：`data/processed/stage07/research/alexandria_hotel/official.txt`、`la_times/official_supplement.txt`、`hall_records/official_supplement.txt`、`la_theatre/official.txt`。原始HTML及取得回执留在对应`data/raw/stage07/research`目录。网页上的远程版权照片未在此复制。
- 补充百科本地文本：`data/raw/stage07_revision/{alexandria,arcade,records,times,theatre}.txt`；每个文本对应`*_wiki.json`和API请求回执。百科文字是二级建筑叙述，不能升级为测绘尺寸或官方确认。
- Times有效入口为`https://www.laconservancy.org/learn/historic-places/times-mirror-square/`；Hall有效入口为`https://www.laconservancy.org/learn/historic-places/los-angeles-county-hall-of-records/`。Spring Arcade先前两个Conservancy链接均返回404，失败记录继续保留。

## 交付状态应如何表述

五栋可以按上述特征制作有依据的近景近似资产。完成生成、保存重开、开口/法线/尺度和场地衔接检查后，可以分别标记“参考指导的近似完成”，并保留未测尺寸和观察盲区；不能标为“实测复原”或“全部立面资料核实”。其余普通建筑的通用推断窗格仍须保留自己的资料等级，不能因为与这五栋位于同一街区就获得真实性认证。

阶段07的技术或视觉验收结论应绑定实际检查图和当前模型。此资料复核只证明来源解释与可观察特征，不代替最终模型/街景验收，也不证明所有2025–2026改造已经覆盖。

修订模型实际图复查发现剧院原屋顶短边不对应完整装饰立面。最终采用来源最高前部楼厅定位装饰屏，17m宽度与越过最大屋顶投影0.5m均为明确推断；浅门斗0.35m为外观视觉替代，不证明室内通道或精确地籍外墙。远景简化版本也补入随坡基础。
