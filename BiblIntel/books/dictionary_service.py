# books/dictionary_service.py
import re
import json
from pathlib import Path
from nltk.corpus import wordnet as wn

class DictionaryService:
    """Service de dictionnaire avancé utilisant WordNet"""
    
    def __init__(self):
        # Dictionnaire local personnalisé (vous pouvez l'enrichir)
        self.local_dict = self._load_local_dictionary()
    
    def _load_local_dictionary(self):
        """Charge le dictionnaire local personnalisé"""
        return {
            # Termes techniques - Français
            'intelligence': {
                'definition': 'Capacité à comprendre, apprendre et raisonner.',
                'examples': ['Intelligence artificielle', 'Intelligence humaine'],
                'synonyms': ['sagesse', 'compréhension']
            },
            'artificielle': {
                'definition': 'Qui est produit par l\'homme, non naturel.',
                'examples': ['Intelligence artificielle', 'Fleur artificielle']
            },
            'apprentissage': {
                'definition': 'Processus d\'acquisition de connaissances.',
                'examples': ['Apprentissage automatique', 'Apprentissage profond']
            },
            'deep learning': {
                'definition': 'Méthode d\'apprentissage basée sur des réseaux de neurones profonds.',
                'examples': ['Réseaux profonds', 'Deep learning en vision']
            },
            'machine learning': {
                'definition': 'Domaine de l\'IA utilisant des algorithmes statistiques.',
                'examples': ['Classification', 'Régression', 'Clustering']
            },
            'réseau': {
                'definition': 'Ensemble d\'éléments interconnectés.',
                'examples': ['Réseau informatique', 'Réseau de neurones']
            },
            'neurone': {
                'definition': 'Cellule nerveuse qui transmet des signaux électriques.',
                'examples': ['Neurone biologique', 'Neurone artificiel']
            },
            'algorithme': {
                'definition': 'Suite d\'opérations pour résoudre un problème.',
                'examples': ['Algorithme de tri', 'Algorithme de recherche']
            },
            'donnée': {
                'definition': 'Information brute qui peut être traitée.',
                'examples': ['Base de données', 'Analyse de données']
            },
            'modèle': {
                'definition': 'Représentation simplifiée d\'un système.',
                'examples': ['Modèle mathématique', 'Modèle de données']
            },
            
            # Termes techniques - English
            'intelligence': {
                'definition': 'Ability to acquire and apply knowledge.',
                'examples': ['Artificial Intelligence']
            },
            'algorithm': {
                'definition': 'Step-by-step procedure for solving a problem.',
                'examples': ['Sorting algorithm', 'Search algorithm']
            },
            'neural network': {
                'definition': 'Computing system inspired by biological neural networks.',
                'examples': ['Deep neural network', 'Convolutional network']
            },
            
            # Génie civil
            'béton': {
                'definition': 'Matériau de construction composé de ciment, sable, gravier et eau.',
                'examples': ['Béton armé', 'Béton précontraint']
            },
            'résistance': {
                'definition': 'Capacité d\'un matériau à supporter des contraintes.',
                'examples': ['Résistance des matériaux', 'Résistance mécanique']
            },
            
            # Électronique
            'circuit': {
                'definition': 'Ensemble de composants électroniques connectés.',
                'examples': ['Circuit imprimé', 'Circuit intégré']
            },
            'tension': {
                'definition': 'Différence de potentiel électrique.',
                'examples': ['Tension alternative', 'Tension continue']
            },
            
            # Littérature
            'dystopie': {
                'definition': 'Société fictive caractérisée par un régime totalitaire.',
                'examples': ['1984', 'Le Meilleur des mondes']
            },
            'philosophique': {
                'definition': 'Relatif à la philosophie, à la réflexion sur le sens de la vie.',
                'examples': ['Conte philosophique', 'Réflexion philosophique']
            }
        }
    
    def get_definition(self, word):
        """Récupère la définition d'un mot"""
        word_lower = word.lower().strip()
        
        # 1. Chercher dans le dictionnaire local d'abord
        if word_lower in self.local_dict:
            return self.local_dict[word_lower]
        
        # 2. Chercher dans WordNet
        synsets = wn.synsets(word_lower)
        
        if synsets:
            # Prendre la première définition
            best_match = synsets[0]
            definition = best_match.definition()
            
            # Récupérer les exemples
            examples = best_match.examples()
            
            # Récupérer les synonymes
            synonyms = [lemma.name() for lemma in best_match.lemmas()[:5]]
            
            return {
                'definition': definition.capitalize(),
                'examples': examples if examples else [],
                'synonyms': synonyms if synonyms else [],
                'part_of_speech': self._get_pos_name(best_match.pos())
            }
        
        # 3. Aucune définition trouvée
        return None
    
    def _get_pos_name(self, pos_code):
        """Convertit le code de partie de discours en nom lisible"""
        pos_map = {
            'n': 'nom',
            'v': 'verbe',
            'a': 'adjectif',
            'r': 'adverbe',
            's': 'adjectif satellite'
        }
        return pos_map.get(pos_code, 'mot')
    
    def get_synonyms(self, word):
        """Récupère les synonymes d'un mot"""
        word_lower = word.lower().strip()
        
        synonyms = set()
        for synset in wn.synsets(word_lower):
            for lemma in synset.lemmas():
                if lemma.name() != word_lower:
                    synonyms.add(lemma.name().replace('_', ' '))
        
        return list(synonyms)[:10]
    
    def get_antonyms(self, word):
        """Récupère les antonymes d'un mot"""
        word_lower = word.lower().strip()
        antonyms = []
        
        for synset in wn.synsets(word_lower):
            for lemma in synset.lemmas():
                if lemma.antonyms():
                    for ant in lemma.antonyms():
                        antonyms.append(ant.name().replace('_', ' '))
        
        return list(set(antonyms))[:5]
    
    def get_word_family(self, word):
        """Récupère la famille de mots (verbe, nom, adjectif, adverbe)"""
        word_lower = word.lower().strip()
        family = {}
        
        for synset in wn.synsets(word_lower):
            pos = synset.pos()
            pos_name = self._get_pos_name(pos)
            if pos_name not in family:
                family[pos_name] = []
                for lemma in synset.lemmas():
                    family[pos_name].append(lemma.name().replace('_', ' '))
        
        return family
    
    def search_words(self, query, limit=20):
        """Recherche des mots correspondant à une requête"""
        query_lower = query.lower()
        results = []
        
        # Chercher dans WordNet
        for synset in wn.all_synsets():
            if query_lower in synset.name():
                results.append({
                    'word': synset.name().split('.')[0],
                    'definition': synset.definition()
                })
                if len(results) >= limit:
                    break
        
        # Chercher dans le dictionnaire local
        for word, data in self.local_dict.items():
            if query_lower in word or query_lower in data.get('definition', '').lower():
                results.append({
                    'word': word,
                    'definition': data['definition']
                })
                if len(results) >= limit:
                    break
        
        return results[:limit]


# Instance unique
dictionary_service = DictionaryService()