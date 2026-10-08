"""Taxonomía de la biblioteca: género (nivel 1) › subgénero (nivel 2). Cada subgénero lleva una frase en español y otra en inglés: con ellas el clasificador por parecido
decide el subgénero entre los de su género (y el LLM, si hay duda, elige entre ellos). Se amplía sin tocar el código con `conocimiento/taxonomia.json` (ver `cargar`).

Formato de GENEROS_NUEVOS y TAXONOMIA: id -> (nombre, [(subid, nombre, frase_es, frase_en), ...]).
"""
from __future__ import annotations

import json
from pathlib import Path

# Géneros que se añaden a los 11 de siempre (historia, economia, ensayo, estadistica, ciencia, novela, biografia, politica, tecnologia, psicologia, arte, otro).
GENEROS_NUEVOS = {
    "derecho": "Derecho y legislación", "cocina": "Cocina y gastronomía", "salud": "Salud y medicina", "viajes": "Viajes y geografía",
    "idiomas": "Idiomas y lingüística", "educacion": "Educación y pedagogía", "religion": "Religión y espiritualidad", "deporte": "Deporte y ocio",
    "hogar": "Hogar, jardín y bricolaje", "literatura": "Literatura (poesía, teatro, cuentos)",
}

TAXONOMIA: dict[str, list[tuple[str, str, str, str]]] = {
    "historia": [
        ("antigua", "Roma, Grecia y mundo antiguo", "Roma antigua, Grecia clásica, Egipto, César, Alejandro Magno, imperios del mundo antiguo", "ancient Rome, classical Greece, Egypt, the Roman Republic and Empire, Alexander the Great"),
        ("medieval", "Edad Media", "Edad Media, feudalismo, cruzadas, caballeros, Bizancio, el islam medieval y las monarquías", "medieval history, feudalism, the Crusades, knights, Byzantium, the Middle Ages"),
        ("moderna", "Edad Moderna y Renacimiento", "Renacimiento, Reforma, descubrimientos, imperios coloniales, absolutismo y siglo XVIII", "Renaissance, Reformation, age of discovery, early modern Europe, absolutism and Enlightenment"),
        ("revoluciones", "Revoluciones y siglo XIX", "Revolución francesa, Napoleón, revoluciones liberales, imperialismo e industrialización del siglo XIX", "French Revolution, Napoleon, nineteenth century, imperialism and industrialization"),
        ("guerras_mundiales", "Guerras mundiales y siglo XX", "Primera y Segunda Guerra Mundial, nazismo, Guerra Fría, Holocausto y el siglo XX", "World War I and II, Nazi Germany, the Cold War, the Holocaust and the twentieth century"),
        ("espana", "Historia de España", "Historia de España, Reconquista, Reyes Católicos, Imperio español, Guerra Civil y transición", "history of Spain, Reconquista, Spanish Empire, Civil War and Franco"),
        ("america", "Historia de América", "Historia de América, conquista, independencias, Estados Unidos, Latinoamérica y culturas precolombinas", "history of the Americas, conquest, independence, United States, Latin America, pre-Columbian cultures"),
        ("militar", "Historia militar", "Batallas, estrategia militar, ejércitos, campañas y generales a lo largo de la historia", "military history, battles, strategy, armies, campaigns and generals"),
        ("ideas", "Historia de las ideas y de la ciencia", "Historia de las ideas, de la ciencia, de la filosofía y de las religiones", "history of ideas, of science, of philosophy and religion"),
        ("arqueologia", "Arqueología y antropología", "Arqueología, prehistoria, civilizaciones perdidas, antropología y orígenes de la humanidad", "archaeology, prehistory, lost civilizations, anthropology and the origins of humankind"),
    ],
    "economia": [
        ("macro", "Macroeconomía", "Macroeconomía: PIB, inflación, desempleo, política monetaria y fiscal, ciclos económicos y banca central", "macroeconomics: GDP, inflation, unemployment, monetary and fiscal policy, business cycles, central banks"),
        ("micro", "Microeconomía", "Microeconomía: oferta y demanda, elasticidad, consumidores, empresas, mercados y teoría de juegos", "microeconomics: supply and demand, elasticity, consumers, firms, markets and game theory"),
        ("inversion", "Inversión y bolsa", "Invertir en bolsa, acciones, fondos indexados, análisis fundamental y técnico, gestión de carteras", "investing in the stock market, shares, index funds, fundamental and technical analysis, portfolio management"),
        ("finanzas", "Finanzas corporativas y valoración", "Finanzas corporativas, valoración de empresas, flujos de caja descontados, estructura de capital", "corporate finance, company valuation, discounted cash flow, capital structure"),
        ("derivados", "Derivados y riesgo", "Derivados financieros, opciones, futuros, gestión del riesgo, VaR y mercados de renta fija", "derivatives, options, futures, risk management, value at risk and fixed income markets"),
        ("negocios", "Empresa, emprendimiento y marketing", "Emprendimiento, estrategia empresarial, liderazgo, marketing, ventas y gestión de equipos", "entrepreneurship, business strategy, leadership, marketing, sales and management"),
        ("desarrollo", "Desarrollo, pobreza y desigualdad", "Desarrollo económico, pobreza, desigualdad, globalización, comercio internacional y países en desarrollo", "economic development, poverty, inequality, globalization, international trade"),
        ("historia_eco", "Historia y pensamiento económico", "Historia del pensamiento económico, Adam Smith, Marx y crisis históricas, la evolución de la economía como disciplina", "history of economic thought, Adam Smith, Marx and historical crises, the evolution of economics as a discipline"),
        ("teoria_eco", "Teoría y escuelas económicas", "Teoría económica y escuelas: economía austriaca, praxeología, capital e interés, ciclo económico, Mises, Hayek, keynesianismo y monetarismo", "economic theory and schools: Austrian economics, praxeology, capital and interest, business cycle theory, Mises, Hayek, Keynesianism and monetarism"),
        ("cripto", "Criptomonedas y fintech", "Bitcoin, criptomonedas, blockchain, finanzas descentralizadas y tecnología financiera", "Bitcoin, cryptocurrencies, blockchain, decentralized finance and fintech"),
        ("contabilidad", "Contabilidad y banca", "Contabilidad, balances, auditoría, banca, seguros y regulación financiera", "accounting, balance sheets, auditing, banking, insurance and financial regulation"),
    ],
    "ensayo": [
        ("antigua", "Filosofía antigua y estoicismo", "Filosofía griega, Platón, Aristóteles, estoicismo, Marco Aurelio, Séneca y epicureísmo", "ancient philosophy, Plato, Aristotle, Stoicism, Marcus Aurelius, Seneca and Epicureanism"),
        ("moderna", "Filosofía moderna y razón", "Filosofía moderna, Descartes, Kant, Hume, racionalismo, empirismo e Ilustración", "modern philosophy, Descartes, Kant, Hume, rationalism, empiricism and Enlightenment"),
        ("existencialismo", "Existencialismo y absurdo", "Existencialismo, Nietzsche, Sartre, Camus, el sentido de la vida, la libertad y el absurdo", "existentialism, Nietzsche, Sartre, Camus, the meaning of life, freedom and the absurd"),
        ("etica", "Ética y moral", "Ética, moral, virtud, justicia, deberes y dilemas morales", "ethics, morality, virtue, justice, duty and moral dilemmas"),
        ("politica_fil", "Filosofía política y sociedad", "Filosofía política, libertad, contrato social, estado, Mill, Locke, Rawls y justicia social", "political philosophy, liberty, social contract, the state, Mill, Locke, Rawls"),
        ("logica", "Lógica y filosofía de la ciencia", "Lógica, epistemología, filosofía de la ciencia, conocimiento, verdad y método científico", "logic, epistemology, philosophy of science, knowledge, truth and scientific method"),
        ("sabiduria", "Sabiduría oriental y vida buena", "Filosofía oriental, budismo, taoísmo, sabiduría práctica, mindfulness y cómo vivir una buena vida", "Eastern philosophy, Buddhism, Taoism, practical wisdom, mindfulness and how to live well"),
        ("ensayo_lit", "Ensayo literario y crítica cultural", "Ensayos personales, crítica cultural, reflexiones sobre la sociedad, la tecnología y la época", "personal essays, cultural criticism, reflections on society, technology and our times"),
    ],
    "estadistica": [
        ("probabilidad", "Probabilidad y procesos", "Probabilidad, variables aleatorias, distribuciones, esperanza, cadenas de Markov y procesos estocásticos", "probability, random variables, distributions, expectation, Markov chains and stochastic processes"),
        ("inferencia", "Inferencia y contrastes", "Inferencia estadística, estimación, intervalos de confianza, contrastes de hipótesis y verosimilitud", "statistical inference, estimation, confidence intervals, hypothesis testing and likelihood"),
        ("regresion", "Regresión y modelos lineales", "Regresión lineal y logística, modelos lineales generalizados, ANOVA, residuos y selección de variables", "linear and logistic regression, generalized linear models, ANOVA, residuals and variable selection"),
        ("bayes", "Estadística bayesiana", "Estadística bayesiana, distribuciones a priori y a posteriori, MCMC y modelos jerárquicos", "Bayesian statistics, prior and posterior distributions, MCMC and hierarchical models"),
        ("series", "Series temporales y previsión", "Series temporales, ARIMA, estacionalidad, autocorrelación, previsión y modelos de volatilidad", "time series, ARIMA, seasonality, autocorrelation, forecasting and volatility models"),
        ("ml_est", "Aprendizaje estadístico y minería de datos", "Aprendizaje estadístico, clasificación, árboles, bosques aleatorios, validación cruzada y reducción de dimensión", "statistical learning, classification, trees, random forests, cross-validation and dimension reduction"),
        ("muestreo", "Muestreo, diseño y encuestas", "Muestreo, encuestas, diseño de experimentos, ensayos clínicos y análisis causal", "sampling, surveys, design of experiments, clinical trials and causal inference"),
        ("supervivencia", "Supervivencia, actuarial y fiabilidad", "Análisis de supervivencia, matemática actuarial, tablas de vida, seguros y fiabilidad", "survival analysis, actuarial mathematics, life tables, insurance and reliability"),
        ("algebra", "Álgebra lineal", "Álgebra lineal, matrices, espacios vectoriales, valores propios y descomposiciones", "linear algebra, matrices, vector spaces, eigenvalues and decompositions"),
        ("analisis", "Cálculo y análisis", "Cálculo diferencial e integral, análisis real, ecuaciones diferenciales y optimización", "calculus, real analysis, differential equations and optimization"),
        ("discreta", "Matemática discreta y lógica", "Matemática discreta, combinatoria, grafos, teoría de números, lógica y demostraciones", "discrete mathematics, combinatorics, graphs, number theory, logic and proofs"),
    ],
    "ciencia": [
        ("fisica", "Física", "Física, mecánica, relatividad, física cuántica, partículas y termodinámica", "physics, mechanics, relativity, quantum physics, particles and thermodynamics"),
        ("cosmos", "Astronomía y cosmología", "Astronomía, cosmología, el universo, agujeros negros, planetas, estrellas y exploración espacial", "astronomy, cosmology, the universe, black holes, planets, stars and space exploration"),
        ("quimica", "Química y materiales", "Química, elementos, reacciones, materiales y tabla periódica", "chemistry, elements, reactions, materials and the periodic table"),
        ("biologia", "Biología y evolución", "Biología, evolución, selección natural, genética, ADN, células y origen de la vida", "biology, evolution, natural selection, genetics, DNA, cells and the origin of life"),
        ("neuro", "Neurociencia y mente", "Neurociencia, cerebro, memoria, conciencia, sueño y funcionamiento de la mente", "neuroscience, the brain, memory, consciousness, sleep and how the mind works"),
        ("ecologia", "Ecología, clima y medio ambiente", "Ecología, cambio climático, medio ambiente, biodiversidad, energía y sostenibilidad", "ecology, climate change, environment, biodiversity, energy and sustainability"),
        ("tierra", "Geología y ciencias de la Tierra", "Geología, la Tierra, volcanes, océanos, paleontología y dinosaurios", "geology, the Earth, volcanoes, oceans, paleontology and dinosaurs"),
        ("divulgacion", "Divulgación y método científico", "Divulgación científica, historia de la ciencia, método científico y grandes descubrimientos", "popular science, history of science, the scientific method and great discoveries"),
    ],
    "novela": [
        ("historica", "Novela histórica", "Novela histórica ambientada en Roma, la Edad Media u otras épocas, con personajes reales y batallas", "historical fiction set in ancient Rome, the Middle Ages or other eras, with real figures and battles"),
        ("negra", "Novela negra y policíaca", "Novela negra, policíaca, detectives, crímenes, asesinatos e investigación", "crime fiction, detective novels, murders and investigation"),
        ("thriller", "Thriller y espionaje", "Thriller, espionaje, conspiraciones, agentes secretos, intriga y suspense", "thriller, espionage, conspiracies, secret agents, intrigue and suspense"),
        ("scifi", "Ciencia ficción", "Ciencia ficción, futuro, viajes espaciales, robots, distopías e inteligencia artificial", "science fiction, the future, space travel, robots, dystopias and artificial intelligence"),
        ("fantasia", "Fantasía", "Fantasía épica, magia, dragones, reinos imaginarios, héroes y mundos inventados", "epic fantasy, magic, dragons, imaginary kingdoms, heroes and invented worlds"),
        ("romance", "Romance y drama", "Novela romántica, historias de amor, relaciones, familia y drama personal", "romance novels, love stories, relationships, family and personal drama"),
        ("clasicos", "Clásicos de la literatura", "Clásicos de la literatura universal, grandes novelas del siglo XIX y XX, realismo y tragedia", "classics of world literature, great nineteenth and twentieth century novels, realism and tragedy"),
        ("terror", "Terror y misterio", "Terror, misterio, lo sobrenatural, fantasmas, monstruos y relatos góticos", "horror, mystery, the supernatural, ghosts, monsters and gothic tales"),
        ("contemporanea", "Narrativa contemporánea", "Narrativa contemporánea, novela actual, relatos y cuentos, realismo mágico", "contemporary fiction, short stories, magical realism and literary novels"),
        ("juvenil", "Juvenil y cómic", "Literatura juvenil, aventuras para jóvenes, cómics y novela gráfica", "young adult fiction, adventure for young readers, comics and graphic novels"),
    ],
    "biografia": [
        ("politicos", "Políticos y líderes", "Biografía de políticos, presidentes, líderes, reyes y emperadores", "biography of politicians, presidents, leaders, kings and emperors"),
        ("cientificos", "Científicos y pensadores", "Biografía de científicos, matemáticos, filósofos e inventores", "biography of scientists, mathematicians, philosophers and inventors"),
        ("artistas", "Artistas y músicos", "Biografía de artistas, pintores, músicos, escritores y actores", "biography of artists, painters, musicians, writers and actors"),
        ("empresarios", "Empresarios e innovadores", "Biografía de empresarios, fundadores, inversores e innovadores tecnológicos", "biography of entrepreneurs, founders, investors and tech innovators"),
        ("espias", "Militares, espías y aventureros", "Memorias de militares, agentes secretos, espías, exploradores y aventureros", "memoirs of soldiers, spies, secret agents, explorers and adventurers"),
        ("deportistas", "Deportistas", "Biografía de deportistas, atletas, futbolistas y entrenadores", "biography of athletes, footballers and coaches"),
        ("memorias", "Memorias y autobiografías", "Memorias personales, autobiografía, historia de vida y relatos en primera persona", "personal memoir, autobiography, life story and first-person narratives"),
    ],
    "politica": [
        ("teoria", "Teoría política", "Teoría política, poder, estado, democracia, ideologías, liberalismo, socialismo y autoritarismo", "political theory, power, the state, democracy, ideologies, liberalism, socialism and authoritarianism"),
        ("internacional", "Relaciones internacionales y geopolítica", "Relaciones internacionales, geopolítica, diplomacia, guerra, alianzas y orden mundial", "international relations, geopolitics, diplomacy, war, alliances and world order"),
        ("instituciones", "Instituciones y políticas públicas", "Instituciones, gobierno, partidos, elecciones, políticas públicas y administración", "institutions, government, parties, elections, public policy and administration"),
        ("seguridad", "Seguridad, inteligencia y terrorismo", "Seguridad nacional, servicios de inteligencia, CIA, terrorismo, espionaje y guerra contra el terror", "national security, intelligence services, the CIA, terrorism, espionage and the war on terror"),
        ("sociologia", "Sociología y sociedad", "Sociología, sociedad, clases sociales, género, migraciones, cultura y cambio social", "sociology, society, social classes, gender, migration, culture and social change"),
        ("nacionalismo", "Nacionalismo e identidad", "Nacionalismo, identidad, naciones, totalitarismo, imperialismo y movimientos políticos", "nationalism, identity, nations, totalitarianism, imperialism and political movements"),
        ("medios", "Medios, propaganda y opinión pública", "Medios de comunicación, periodismo, propaganda, opinión pública y comunicación política", "media, journalism, propaganda, public opinion and political communication"),
        ("persuasion", "Poder y estrategia", "Poder, estrategia, manipulación, persuasión, negociación y liderazgo político", "power, strategy, manipulation, persuasion, negotiation and political leadership"),
    ],
    "tecnologia": [
        ("programacion", "Programación y lenguajes", "Programación, Python, lenguajes, código limpio, funciones y buenas prácticas de desarrollo", "programming, Python, languages, clean code, functions and development best practices"),
        ("ingenieria_sw", "Ingeniería del software", "Ingeniería del software, arquitectura, patrones de diseño, pruebas y metodologías ágiles", "software engineering, architecture, design patterns, testing and agile methodologies"),
        ("datos", "Bases de datos y ciencia de datos", "Bases de datos, SQL, ciencia de datos, análisis de datos con pandas, visualización y ETL", "databases, SQL, data science, data analysis with pandas, visualization and ETL"),
        ("ia", "Inteligencia artificial y aprendizaje profundo", "Inteligencia artificial, redes neuronales, aprendizaje profundo, modelos de lenguaje y visión por computador", "artificial intelligence, neural networks, deep learning, language models and computer vision"),
        ("redes", "Redes, seguridad y sistemas", "Redes, TCP/IP, ciberseguridad, criptografía, sistemas operativos, Linux y administración", "networks, TCP/IP, cybersecurity, cryptography, operating systems, Linux and administration"),
        ("web", "Desarrollo web y móvil", "Desarrollo web, JavaScript, HTML, CSS, frameworks y aplicaciones móviles", "web development, JavaScript, HTML, CSS, frameworks and mobile apps"),
        ("cloud", "Cloud, DevOps y hardware", "Cloud, DevOps, contenedores, infraestructura, electrónica, hardware y sistemas embebidos", "cloud computing, DevOps, containers, infrastructure, electronics, hardware and embedded systems"),
        ("algoritmos", "Algoritmos y estructuras de datos", "Algoritmos, estructuras de datos, complejidad computacional y resolución de problemas", "algorithms, data structures, computational complexity and problem solving"),
        ("sociedad_tec", "Tecnología y sociedad", "Impacto social de la tecnología, internet, redes sociales, privacidad y futuro del trabajo", "social impact of technology, the internet, social media, privacy and the future of work"),
    ],
    "psicologia": [
        ("cognitiva", "Psicología cognitiva y decisiones", "Psicología cognitiva, sesgos, toma de decisiones, pensamiento rápido y lento, racionalidad", "cognitive psychology, biases, decision making, fast and slow thinking, rationality"),
        ("clinica", "Psicología clínica y salud mental", "Psicología clínica, trastornos mentales, ansiedad, depresión, terapia y psicopatología", "clinical psychology, mental disorders, anxiety, depression, therapy and psychopathology"),
        ("emocional", "Emociones y relaciones", "Emociones, inteligencia emocional, relaciones, empatía, apego y comunicación", "emotions, emotional intelligence, relationships, empathy, attachment and communication"),
        ("habitos", "Hábitos, productividad y desarrollo personal", "Hábitos, productividad, motivación, desarrollo personal, disciplina y superación", "habits, productivity, motivation, personal development, discipline and self-improvement"),
        ("social", "Psicología social y del comportamiento", "Psicología social, comportamiento humano, persuasión, influencia, grupos y conformidad", "social psychology, human behavior, persuasion, influence, groups and conformity"),
        ("sentido", "Sentido, bienestar y resiliencia", "Sentido de la vida, felicidad, bienestar, resiliencia, logoterapia y superación del sufrimiento", "meaning of life, happiness, wellbeing, resilience, logotherapy and overcoming suffering"),
        ("sueno", "Sueño, cerebro y salud", "Sueño, descanso, cerebro, estrés, salud mental y hábitos saludables", "sleep, rest, the brain, stress, mental health and healthy habits"),
    ],
    "arte": [
        ("visuales", "Pintura y artes visuales", "Pintura, escultura, fotografía, historia del arte, museos y movimientos artísticos", "painting, sculpture, photography, art history, museums and art movements"),
        ("musica", "Música", "Música, compositores, historia de la música, instrumentos, teoría musical y géneros", "music, composers, history of music, instruments, music theory and genres"),
        ("cine", "Cine y series", "Cine, directores, guion, series de televisión y lenguaje audiovisual", "film, directors, screenwriting, television series and audiovisual language"),
        ("arquitectura", "Arquitectura y diseño", "Arquitectura, urbanismo, diseño gráfico, diseño industrial y funcionalismo", "architecture, urbanism, graphic design, industrial design and functionalism"),
        ("cultura", "Cultura popular y medios", "Cultura popular, medios, humor gráfico, revistas culturales y análisis de la cultura de masas", "popular culture, media, comics and cartoons, cultural magazines and analysis of mass culture"),
        ("ver", "Cómo mirar y entender el arte", "Cómo mirar el arte, interpretar imágenes, publicidad y cultura visual", "how to look at art, interpreting images, advertising and visual culture"),
    ],
    "literatura": [
        ("poesia", "Poesía", "Poesía, poemas, versos, sonetos, poetas, romancero, antologías poéticas y prosa poética", "poetry, poems, verse, sonnets, poets, ballads, poetic anthologies and prose poetry"),
        ("teatro", "Teatro y dramaturgia", "Teatro, obras de teatro, comedias, tragedias, dramas, actos y escenas, dramaturgos y personajes que dialogan", "theatre, plays, comedies, tragedies, drama, acts and scenes, playwrights and dialogue between characters"),
        ("cuentos", "Cuentos y relatos breves", "Cuentos, relatos cortos, colecciones de narraciones breves, fábulas, leyendas y cuentos populares", "short stories, tales, collections of short fiction, fables, legends and folk tales"),
        ("critica", "Crítica y ensayo literario", "Crítica literaria, estudios sobre autores y obras, historia de la literatura, teoría literaria y ensayos sobre libros y lectura", "literary criticism, studies of authors and works, history of literature, literary theory and essays on books and reading"),
    ],
    "derecho": [
        ("civil", "Derecho civil y mercantil", "Derecho civil, contratos, propiedad, sociedades mercantiles y obligaciones", "civil law, contracts, property, commercial companies and obligations"),
        ("penal", "Derecho penal y procesal", "Derecho penal, delitos, penas, procesos judiciales y criminología", "criminal law, offences, penalties, court proceedings and criminology"),
        ("constitucional", "Derecho constitucional y administrativo", "Derecho constitucional, derechos fundamentales, administración pública y Unión Europea", "constitutional law, fundamental rights, public administration and the European Union"),
        ("fiscal", "Fiscalidad y derecho laboral", "Fiscalidad, impuestos, derecho laboral, seguridad social y normativa bancaria", "taxation, taxes, labour law, social security and banking regulation"),
        ("internacional_der", "Derecho internacional", "Derecho internacional, tratados, derechos humanos y justicia internacional", "international law, treaties, human rights and international justice"),
    ],
    "cocina": [
        ("recetas", "Recetas", "Recetas de cocina, ingredientes, platos, pasta, arroz, carnes y postres", "recipes, ingredients, dishes, pasta, rice, meat and desserts"),
        ("tecnica", "Técnica culinaria y repostería", "Técnicas de cocina, repostería, panadería, cocina molecular y chefs", "cooking techniques, pastry, baking, molecular gastronomy and chefs"),
        ("vino", "Vino, bebidas y cultura gastronómica", "Vino, cerveza, café, bebidas, enología y cultura gastronómica", "wine, beer, coffee, drinks, oenology and food culture"),
        ("nutricion", "Nutrición y dietas", "Nutrición, dietas, alimentación saludable, ayuno y ciencia de los alimentos", "nutrition, diets, healthy eating, fasting and food science"),
    ],
    "salud": [
        ("medicina", "Medicina y enfermedades", "Medicina, enfermedades, diagnóstico, tratamiento, anatomía y fisiología", "medicine, diseases, diagnosis, treatment, anatomy and physiology"),
        ("epidemiologia", "Salud pública y epidemiología", "Salud pública, epidemiología, vacunas, pandemias y sistemas sanitarios", "public health, epidemiology, vaccines, pandemics and health systems"),
        ("ejercicio", "Ejercicio y bienestar físico", "Ejercicio físico, entrenamiento, fitness, longevidad y bienestar", "physical exercise, training, fitness, longevity and wellbeing"),
        ("alternativa", "Medicina integrativa y cuidados", "Cuidados, enfermería, medicina integrativa, primeros auxilios y envejecimiento", "care, nursing, integrative medicine, first aid and ageing"),
    ],
    "viajes": [
        ("guias", "Guías de viaje", "Guías de viaje, destinos, itinerarios, ciudades, turismo y consejos para viajar", "travel guides, destinations, itineraries, cities, tourism and travel tips"),
        ("relatos", "Relatos de viaje y exploración", "Relatos de viajes, exploradores, aventuras, expediciones y crónicas", "travel writing, explorers, adventures, expeditions and chronicles"),
        ("geografia", "Geografía y mapas", "Geografía, mapas, países, regiones, cartografía y geografía humana", "geography, maps, countries, regions, cartography and human geography"),
    ],
    "idiomas": [
        ("aprendizaje", "Aprender idiomas", "Aprender idiomas, gramática, vocabulario, inglés, francés, italiano y métodos de estudio", "learning languages, grammar, vocabulary, English, French, Italian and study methods"),
        ("linguistica", "Lingüística y escritura", "Lingüística, etimología, historia de las lenguas, redacción y estilo de escritura", "linguistics, etymology, history of languages, writing and style"),
    ],
    "educacion": [
        ("pedagogia", "Pedagogía y enseñanza", "Pedagogía, enseñanza, didáctica, aprendizaje, docentes y sistemas educativos", "pedagogy, teaching, didactics, learning, teachers and education systems"),
        ("estudio", "Técnicas de estudio y oposiciones", "Técnicas de estudio, memoria, oposiciones, exámenes, orientación académica y universidad", "study techniques, memory, exams, academic guidance and university"),
        ("apuntes", "Apuntes y material de curso", "Apuntes de clase, horarios, temarios, guías docentes y material de asignaturas", "class notes, timetables, syllabi, course guides and subject material"),
    ],
    "religion": [
        ("cristianismo", "Cristianismo y Biblia", "Cristianismo, Biblia, teología, iglesia, Jesús y espiritualidad cristiana", "Christianity, the Bible, theology, the church, Jesus and Christian spirituality"),
        ("otras", "Otras religiones y mitología", "Islam, judaísmo, budismo, hinduismo, mitología, religiones comparadas y esoterismo", "Islam, Judaism, Buddhism, Hinduism, mythology, comparative religion and esotericism"),
    ],
    "deporte": [
        ("deportes", "Deportes y entrenamiento", "Deportes, fútbol, baloncesto, tenis, ciclismo, running, entrenamiento y competición", "sports, football, basketball, tennis, cycling, running, training and competition"),
        ("juegos", "Juegos, ajedrez y ocio", "Juegos, ajedrez, videojuegos, juegos de mesa, aficiones y ocio", "games, chess, video games, board games, hobbies and leisure"),
    ],
    "hogar": [
        ("bricolaje", "Bricolaje y manualidades", "Bricolaje, reparaciones, carpintería, manualidades y herramientas", "DIY, repairs, carpentry, crafts and tools"),
        ("jardin", "Jardín y huerto", "Jardinería, plantas, huerto, árboles y cuidado del jardín", "gardening, plants, vegetable garden, trees and garden care"),
        ("organizacion", "Organización del hogar y finanzas personales", "Organización del hogar, orden, minimalismo, ahorro y finanzas personales", "home organization, decluttering, minimalism, saving and personal finance"),
    ],
}


def cargar(carpeta: Path | str | None = None) -> tuple[dict, dict]:
    """(géneros nuevos {id: nombre}, taxonomía {género: [(subid, nombre, frase_es, frase_en)]}) más lo que añadas tú en `conocimiento/taxonomia.json`:
    {"generos": {"id": "Nombre"}, "sub": {"genero": [{"id": "x", "nombre": "…", "frases": ["…", "…"]}]}}. Tus subgéneros se suman (mismo id = sustituye)."""
    generos, tax = dict(GENEROS_NUEVOS), {g: list(v) for g, v in TAXONOMIA.items()}
    if carpeta is not None:
        try:
            mio = json.loads((Path(carpeta) / "taxonomia.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            mio = {}
        generos.update(mio.get("generos", {}))
        for g, subs in mio.get("sub", {}).items():
            actuales = {s[0]: s for s in tax.setdefault(g, [])}
            for s in subs:
                fr = s.get("frases", [])
                actuales[s["id"]] = (s["id"], s.get("nombre", s["id"]), fr[0] if fr else s.get("nombre", ""), fr[1] if len(fr) > 1 else (fr[0] if fr else ""))
            tax[g] = list(actuales.values())
    return generos, tax


def subgeneros(genero: str, carpeta: Path | str | None = None) -> list[tuple[str, str, str, str]]:
    """[(subid, nombre, frase_es, frase_en)] del género (con lo que hayas añadido en taxonomia.json); [] si el género no tiene."""
    return cargar(carpeta)[1].get(genero, [])


def nombre_sub(genero: str, subid: str, carpeta: Path | str | None = None) -> str:
    return next((s[1] for s in subgeneros(genero, carpeta) if s[0] == subid), "")


if __name__ == "__main__":
    print(sum(len(v) for v in TAXONOMIA.values()), "subgéneros en", len(TAXONOMIA), "géneros")
