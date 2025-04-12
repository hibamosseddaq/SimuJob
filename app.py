from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import json
import datetime
import random
import pandas as pd
import sqlite3
import time
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'simujob_secret_key_2025'  # à remplacer par une clé secrète plus sécurisée en production

# Configuration de la base de données
DATABASE = 'simujob.db'


# Chargement des questions depuis le fichier Excel
def load_questions_from_excel():
    try:
        df = pd.read_excel('questions.xlsx')
        questions_by_job = {}

        for _, row in df.iterrows():
            job = row['Poste']
            question = row['Question']
            reponse = row['Reponse']

            if job not in questions_by_job:
                questions_by_job[job] = []

            questions_by_job[job].append({
                'question': question,
                'reponse': reponse
            })

        return questions_by_job
    except Exception as e:
        print(f"Erreur lors du chargement des questions: {e}")
        return {}


# Variables globales
QUESTIONS_BY_JOB = load_questions_from_excel()
JOBS = list(QUESTIONS_BY_JOB.keys())


# Fonctions utilitaires pour la base de données
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()

    # Création de la table utilisateurs
    conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL,
        etablissement TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Création de la table admins pour le panneau d'administration
    conn.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )
    ''')

    # Création de la table simulations pour stocker les résultats
    conn.execute('''
    CREATE TABLE IF NOT EXISTS simulations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job TEXT NOT NULL,
        score REAL NOT NULL,
        duration INTEGER NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Création de la table questions (pour garder une trace si nécessaire)
    conn.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poste TEXT NOT NULL,
        question TEXT NOT NULL,
        reponse TEXT NOT NULL
    )
    ''')

    # Création de la table réponses des utilisateurs
    conn.execute('''
    CREATE TABLE IF NOT EXISTS user_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        simulation_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        user_answer TEXT NOT NULL,
        model_answer TEXT NOT NULL,
        score REAL NOT NULL,
        label TEXT NOT NULL,
        feedback TEXT NOT NULL,
        FOREIGN KEY (simulation_id) REFERENCES simulations (id)
    )
    ''')

    # Insertion d'un admin par défaut si aucun n'existe
    admin_exists = conn.execute('SELECT COUNT(*) FROM admins').fetchone()[0]
    if admin_exists == 0:
        conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)',
                     ('admin', generate_password_hash('admin2025')))

    conn.commit()
    conn.close()


# Initialisation de la base de données au démarrage de l'application
with app.app_context():
    init_db()


# Analyseur de réponses basique
def analyze_answer(user_answer, model_answer):
    # Calcul d'un score simple basé sur le nombre de mots-clés communs
    user_words = set(user_answer.lower().split())
    model_words = set(model_answer.lower().split())

    common_words = user_words.intersection(model_words)
    score = min(100, int(len(common_words) / len(model_words) * 100))

    # Définir le sentiment en fonction du score
    if score >= 70:
        label = "POSITIVE"
        feedback = "Excellente réponse! Vous avez abordé les points essentiels et démontré une bonne compréhension du sujet."
    elif score >= 50:
        label = "NEUTRAL"
        feedback = "Bonne réponse avec quelques éléments clés, mais certains aspects importants pourraient être développés davantage."
    else:
        label = "NEGATIVE"
        feedback = "Votre réponse pourrait être améliorée en abordant plus d'aspects clés du sujet et en fournissant des exemples concrets."

    return {
        'score': score,
        'label': label,
        'feedback': feedback
    }


# Routes de l'application
@app.route('/')
def index():
    return render_template('index.html', jobs=JOBS)


@app.route('/entretien', methods=['POST'])
def entretien():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        etablissement = request.form['etablissement']
        job = request.form['job']

        # Enregistrement des informations utilisateur en session
        session['username'] = username
        session['email'] = email
        session['etablissement'] = etablissement
        session['job'] = job
        session['start_time'] = time.time()

        # Vérification que le job est valide et dans notre liste
        if job not in JOBS:
            flash("Le poste sélectionné n'est pas disponible.")
            return redirect(url_for('index'))

        # Enregistrement de l'utilisateur dans la base de données
        conn = get_db_connection()
        user_id = conn.execute('INSERT INTO users (username, email, etablissement) VALUES (?, ?, ?)',
                               (username, email, etablissement)).lastrowid
        conn.commit()
        conn.close()

        session['user_id'] = user_id
        # Sélection aléatoire de 5 questions pour ce poste
        job_questions = QUESTIONS_BY_JOB.get(job, [])
        if len(job_questions) > 15:
            selected_questions = random.sample(job_questions, 15)
        else:
            selected_questions = job_questions

        # Stockage des questions et réponses en session
        session['question_data'] = selected_questions
        session['questions'] = [q['question'] for q in selected_questions]

        return render_template('entretien.html', questions=session['questions'], username=username, job=job)


@app.route('/resultat', methods=['POST', 'GET'])
def resultat():
    if request.method == 'POST':
        # Récupération des réponses utilisateur
        answers = []

        # Récupérer toutes les réponses du formulaire
        for i in range(len(session['questions'])):
            question_id = request.form.getlist('question_id')[i]
            answer = request.form.getlist('answer')[i]
            answers.append({
                'question_id': question_id,
                'answer': answer
            })

        # Calculer la durée de l'entretien
        end_time = time.time()
        duration = int((end_time - session['start_time']) / 60)  # en minutes

        # Analyser les réponses et calculer le score
        results = []
        total_score = 0

        # Préparer la connection à la BD
        conn = get_db_connection()

        # Créer une entrée dans la table simulations
        simulation_id = conn.execute(
            'INSERT INTO simulations (user_id, job, score, duration) VALUES (?, ?, ?, ?)',
            (session['user_id'], session['job'], 0, duration)  # Score temporaire à 0
        ).lastrowid

        # Pour chaque réponse, analyser et calculer un score
        for i, ans in enumerate(answers):
            question_index = int(ans['question_id'])
            user_answer = ans['answer']
            question = session['questions'][question_index]
            model_answer = session['question_data'][question_index]['reponse']

            # Analyser la réponse
            analysis = analyze_answer(user_answer, model_answer)

            # Stocker le résultat
            results.append({
                'question': question,
                'answer': user_answer,
                'score': analysis['score'],
                'label': analysis['label'],
                'feedback': analysis['feedback']
            })

            # Ajouter au score total
            total_score += analysis['score']

            # Enregistrer la réponse dans la BD
            conn.execute(
                'INSERT INTO user_answers (simulation_id, question_id, question_text, user_answer, model_answer, score, label, feedback) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (simulation_id, question_index, question, user_answer, model_answer, analysis['score'],
                 analysis['label'], analysis['feedback'])
            )

        # Calculer le score global
        overall_score = int(total_score / len(answers))

        # Mettre à jour le score final dans la table simulations
        conn.execute(
            'UPDATE simulations SET score = ? WHERE id = ?',
            (overall_score, simulation_id)
        )

        conn.commit()
        conn.close()

        # Stocker les résultats en session pour les pages suivantes
        session['results'] = results
        session['overall_score'] = overall_score
        session['interview_duration'] = duration
        session['simulation_id'] = simulation_id

        return render_template(
            'resultat.html',
            username=session['username'],
            job=session['job'],
            results=results,
            overall_score=overall_score,
            interview_duration=duration
        )
    else:
        # Si la méthode est GET, vérifier si les résultats sont en session
        if 'results' in session:
            return render_template(
                'resultat.html',
                username=session['username'],
                job=session['job'],
                results=session['results'],
                overall_score=session['overall_score'],
                interview_duration=session['interview_duration']
            )
        else:
            return redirect(url_for('index'))


@app.route('/voir_resultats')
def voir_resultats():
    if 'simulation_id' not in session:
        return redirect(url_for('index'))

    # Récupérer toutes les réponses pour cette simulation
    conn = get_db_connection()
    resultats = conn.execute(
        '''SELECT q.question_text as question, q.user_answer as reponse_utilisateur, 
           q.model_answer as bonne_reponse, q.feedback 
           FROM user_answers q 
           WHERE q.simulation_id = ?''',
        (session['simulation_id'],)
    ).fetchall()
    conn.close()

    # Convertir les résultats en liste de dictionnaires pour la template
    resultats_list = []
    for row in resultats:
        resultats_list.append({
            'question': row['question'],
            'reponse_utilisateur': row['reponse_utilisateur'],
            'bonne_reponse': row['bonne_reponse'],
            'feedback': row['feedback']
        })

    return render_template(
        'voir_resultats.html',
        username=session['username'],
        job=session['job'],
        resultats=resultats_list
    )


@app.route('/conseils')
def conseils():
    if 'job' not in session:
        return redirect(url_for('index'))

    return render_template('conseils.html', job=session['job'])


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (username,)).fetchone()
        conn.close()

        if admin and check_password_hash(admin['password'], password):
            session['admin'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect')
            return redirect(url_for('admin_login'))

    return render_template('login.html')


@app.route('/admin')
def admin():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    # Statistiques générales
    stats = {}
    stats['total_users'] = conn.execute('SELECT COUNT(DISTINCT user_id) FROM simulations').fetchone()[0]
    stats['total_interviews'] = conn.execute('SELECT COUNT(*) FROM simulations').fetchone()[0]
    stats['total_institutions'] = conn.execute('SELECT COUNT(DISTINCT etablissement) FROM users').fetchone()[0]
    stats['average_score'] = conn.execute('SELECT AVG(score) FROM simulations').fetchone()[0]
    if stats['average_score'] is None:
        stats['average_score'] = 0
    stats['average_score'] = round(stats['average_score'])

    # Liste des utilisateurs récents
    users = conn.execute('''
        SELECT u.username, u.email, u.etablissement, s.job, s.score, 
               datetime(s.date) as date
        FROM users u
        JOIN simulations s ON u.id = s.user_id
        ORDER BY s.date DESC
        LIMIT 50
    ''').fetchall()

    # Scores par poste
    job_stats = conn.execute('''
        SELECT job, AVG(score) as avg_score, COUNT(*) as count
        FROM simulations
        GROUP BY job
    ''').fetchall()

    job_names = [j['job'] for j in job_stats]
    job_scores = [round(j['avg_score']) for j in job_stats]

    # Entretiens par jour (7 derniers jours)
    today = datetime.datetime.now().date()
    dates = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]

    interviews_per_day = []
    for date in dates:
        count = conn.execute('''
            SELECT COUNT(*) FROM simulations
            WHERE date(date) = ?
        ''', (date,)).fetchone()[0]
        interviews_per_day.append(count)

    # Performance par question (top 10 des questions les moins bien répondues)
    question_stats = conn.execute('''
        SELECT question_text, AVG(score) as avg_score
        FROM user_answers
        GROUP BY question_text
        ORDER BY avg_score ASC
        LIMIT 10
    ''').fetchall()

    question_labels = [q['question_text'][:50] + '...' for q in question_stats]
    question_scores = [round(q['avg_score']) for q in question_stats]

    # Distribution des scores
    score_distribution = [0, 0, 0, 0, 0]  # 0-20%, 21-40%, 41-60%, 61-80%, 81-100%

    scores = conn.execute('SELECT score FROM simulations').fetchall()
    for score in scores:
        if score['score'] <= 20:
            score_distribution[0] += 1
        elif score['score'] <= 40:
            score_distribution[1] += 1
        elif score['score'] <= 60:
            score_distribution[2] += 1
        elif score['score'] <= 80:
            score_distribution[3] += 1
        else:
            score_distribution[4] += 1

    # Performance par établissement
    establishment_stats = conn.execute('''
        SELECT u.etablissement, AVG(s.score) as avg_score
        FROM users u
        JOIN simulations s ON u.id = s.user_id
        GROUP BY u.etablissement
        ORDER BY avg_score DESC
        LIMIT 10
    ''').fetchall()

    establishment_names = [e['etablissement'] for e in establishment_stats]
    establishment_scores = [round(e['avg_score']) for e in establishment_stats]

    # Liste des établissements pour le filtre
    establishments = conn.execute('''
        SELECT DISTINCT etablissement FROM users
        ORDER BY etablissement
    ''').fetchall()
    establishments = [e['etablissement'] for e in establishments]

    # Liste de toutes les questions dans la base de données
    all_questions = []
    for job in JOBS:
        for i, q in enumerate(QUESTIONS_BY_JOB.get(job, [])):
            all_questions.append({
                'id': i,
                'poste': job,
                'question': q['question'],
                'reponse': q['reponse']
            })

    conn.close()

    return render_template(
        'admin.html',
        stats=stats,
        users=users,
        jobs=JOBS,
        job_names=job_names,
        job_scores=job_scores,
        dates=dates,
        interviews_per_day=interviews_per_day,
        question_labels=question_labels,
        question_scores=question_scores,
        score_distribution=score_distribution,
        establishment_names=establishment_names,
        establishment_scores=establishment_scores,
        establishments=establishments,
        all_questions=all_questions
    )


@app.route('/admin/user_details/<username>')
def user_details(username):
    if 'admin' not in session:
        return jsonify({'error': 'Non autorisé'}), 403

    conn = get_db_connection()

    # Récupérer les informations de l'utilisateur
    user = conn.execute('''
        SELECT u.username, u.email, u.etablissement, 
               MAX(datetime(s.date)) as date,
               AVG(s.score) as average_score
        FROM users u
        JOIN simulations s ON u.id = s.user_id
        WHERE u.username = ?
        GROUP BY u.id
    ''', (username,)).fetchone()

    # Récupérer l'historique des simulations
    simulations = conn.execute('''
        SELECT datetime(s.date) as date, s.job, s.score, s.duration
        FROM simulations s
        JOIN users u ON s.user_id = u.id
        WHERE u.username = ?
        ORDER BY s.date DESC
    ''', (username,)).fetchall()

    # Convertir en liste de dictionnaires
    sim_list = []
    for sim in simulations:
        sim_list.append({
            'date': sim['date'],
            'job': sim['job'],
            'score': sim['score'],
            'duration': sim['duration']
        })

    user_dict = dict(user)
    user_dict['simulations'] = sim_list
    user_dict['average_score'] = round(user_dict['average_score'])

    # Performance par compétence (simulée)
    # En réalité, il faudrait avoir une table de compétences associées aux questions
    skill_labels = ["Communication", "Technique", "Résolution de problèmes", "Travail d'équipe", "Leadership"]
    skill_scores = []

    for _ in skill_labels:
        # Score aléatoire pour la démonstration
        score = random.randint(user_dict['average_score'] - 15, user_dict['average_score'] + 15)
        # Limiter le score entre 0 et 100
        score = max(0, min(100, score))
        skill_scores.append(score)

    conn.close()

    return render_template(
        'user_details.html',
        user=user_dict,
        skill_labels=skill_labels,
        skill_scores=skill_scores
    )


@app.route('/admin/get_question/<int:id>')
def get_question(id):
    if 'admin' not in session:
        return jsonify({'error': 'Non autorisé'}), 403

    # Récupérer les informations de la question
    job = None
    question = None
    reponse = None

    for job_name in JOBS:
        questions = QUESTIONS_BY_JOB.get(job_name, [])
        if id < len(questions):
            job = job_name
            question = questions[id]['question']
            reponse = questions[id]['reponse']
            break
        id -= len(questions)

    if question is None:
        return jsonify({'error': 'Question non trouvée'}), 404

    return jsonify({
        'poste': job,
        'question': question,
        'reponse': reponse
    })


@app.route('/admin/add_question', methods=['POST'])
def add_question():
    if 'admin' not in session:
        return jsonify({'error': 'Non autorisé'}), 403

    poste = request.form['poste']
    question = request.form['question']
    reponse = request.form['reponse']

    # Ajouter la question au dictionnaire
    if poste not in QUESTIONS_BY_JOB:
        QUESTIONS_BY_JOB[poste] = []

    QUESTIONS_BY_JOB[poste].append({
        'question': question,
        'reponse': reponse
    })

    # Mettre à jour le fichier Excel
    try:
        all_questions = []
        for job, questions in QUESTIONS_BY_JOB.items():
            for q in questions:
                all_questions.append({
                    'Poste': job,
                    'Question': q['question'],
                    'Reponse': q['reponse']
                })

        df = pd.DataFrame(all_questions)
        df.to_excel('questions.xlsx', index=False)
    except Exception as e:
        print(f"Erreur lors de la mise à jour du fichier Excel: {e}")

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/edit_question', methods=['POST'])
def edit_question():
    if 'admin' not in session:
        return jsonify({'error': 'Non autorisé'}), 403

    question_id = int(request.form['questionId'])
    poste = request.form['poste']
    question = request.form['question']
    reponse = request.form['reponse']

    original_job = None
    original_idx = None

    # Trouver la question à éditer
    idx = question_id
    for job_name in JOBS:
        questions = QUESTIONS_BY_JOB.get(job_name, [])
        if idx < len(questions):
            original_job = job_name
            original_idx = idx
            break
        idx -= len(questions)

    if original_job is None:
        return jsonify({'error': 'Question non trouvée'}), 404

    # Si le poste a changé, supprimer de l'ancien et ajouter au nouveau
    if original_job != poste:
        # Supprimer de l'ancien poste
        del QUESTIONS_BY_JOB[original_job][original_idx]

        # Ajouter au nouveau poste
        if poste not in QUESTIONS_BY_JOB:
            QUESTIONS_BY_JOB[poste] = []

        QUESTIONS_BY_JOB[poste].append({
            'question': question,
            'reponse': reponse
        })
    else:
        # Mettre à jour dans le même poste
        QUESTIONS_BY_JOB[poste][original_idx] = {
            'question': question,
            'reponse': reponse
        }

    # Mettre à jour le fichier Excel
    try:
        all_questions = []
        for job, questions in QUESTIONS_BY_JOB.items():
            for q in questions:
                all_questions.append({
                    'Poste': job,
                    'Question': q['question'],
                    'Reponse': q['reponse']
                })

        df = pd.DataFrame(all_questions)
        df.to_excel('questions.xlsx', index=False)
    except Exception as e:
        print(f"Erreur lors de la mise à jour du fichier Excel: {e}")

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_question/<int:id>', methods=['POST'])
def delete_question(id):
    if 'admin' not in session:
        return jsonify({'error': 'Non autorisé'}), 403

    # Trouver la question à supprimer
    idx = id
    for job_name in JOBS:
        questions = QUESTIONS_BY_JOB.get(job_name, [])
        if idx < len(questions):
            # Supprimer la question
            del QUESTIONS_BY_JOB[job_name][idx]

            # Mettre à jour le fichier Excel
            try:
                all_questions = []
                for job, questions in QUESTIONS_BY_JOB.items():
                    for q in questions:
                        all_questions.append({
                            'Poste': job,
                            'Question': q['question'],
                            'Reponse': q['reponse']
                        })

                df = pd.DataFrame(all_questions)
                df.to_excel('questions.xlsx', index=False)
            except Exception as e:
                print(f"Erreur lors de la mise à jour du fichier Excel: {e}")
                return jsonify({'success': False})

            return jsonify({'success': True})

        idx -= len(questions)

    return jsonify({'success': False})


@app.route('/admin/delete_user/<username>', methods=['POST'])
def delete_user(username):
    if 'admin' not in session:
        return jsonify({'error': 'Non autorisé'}), 403

    conn = get_db_connection()

    try:
        # Récupérer l'ID de l'utilisateur
        user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})

        user_id = user['id']

        # Récupérer les IDs des simulations de l'utilisateur
        simulations = conn.execute('SELECT id FROM simulations WHERE user_id = ?', (user_id,)).fetchall()
        sim_ids = [s['id'] for s in simulations]

        # Supprimer les réponses utilisateur liées aux simulations
        for sim_id in sim_ids:
            conn.execute('DELETE FROM user_answers WHERE simulation_id = ?', (sim_id,))

        # Supprimer les simulations
        conn.execute('DELETE FROM simulations WHERE user_id = ?', (user_id,))

        # Supprimer l'utilisateur
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))

        conn.commit()
        conn.close()

        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        print(f"Erreur lors de la suppression de l'utilisateur: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/admin/update_analytics')
def update_analytics():
    if 'admin' not in session:
        return jsonify({'error': 'Non autorisé'}), 403

    job = request.args.get('job', '')
    date_range = request.args.get('dateRange', '7')

    # Cette fonction serait utilisée pour mettre à jour les graphiques
    # avec des données filtrées. Pour une implémentation complète,
    # il faudrait extraire les données selon les filtres et retourner
    # les résultats en JSON.

    return jsonify({'success': True})


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))


# Gestion des erreurs
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
