import openai
from typing import Dict, List
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import json

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

class FinanceBot:
    def __init__(self):
        # Obtém a chave API do ambiente
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY não encontrada nas variáveis de ambiente")
        
        openai.api_key = self.api_key
        self.conversation_history = []
        
        # Dados históricos médios do S&P 500 como fallback
        self.sp500_historical_return = 0.10  # Retorno médio anual de 10%
        
    def get_euribor_rates(self) -> Dict[str, float]:
        """Obtém as taxas Euribor atuais"""
        try:
            # Fonte: Euribor Rates API
            url = "https://www.euribor-rates.eu/en/current-euribor-rates/"
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            rates = {}
            terms = ['1 week', '1 month', '3 months', '6 months', '12 months']
            
            for term in terms:
                # Adaptar o seletor conforme a estrutura real do site
                rate_element = soup.find(text=lambda t: term in str(t)).find_next('td')
                rate = float(rate_element.text.strip().replace('%', ''))
                rates[term] = rate
                
            return rates
            
        except Exception as e:
            # Valores fallback caso a API falhe
            return {
                "1 week": 3.858,
                "1 month": 3.923,
                "3 months": 3.927,
                "6 months": 3.892,
                "12 months": 3.718
            }

    def get_sp500_performance(self) -> Dict[str, float]:
        """Obtém dados de performance do S&P 500"""
        try:
            # Usando yfinance para obter dados do S&P 500
            sp500 = yf.Ticker("^GSPC")
            
            # Obtém dados dos últimos 10 anos
            end_date = datetime.now()
            start_date = end_date - timedelta(days=3650)  # ~10 anos
            
            hist = sp500.history(start=start_date, end=end_date)
            
            # Calcula retornos
            initial_price = hist['Close'].iloc[0]
            final_price = hist['Close'].iloc[-1]
            total_return = (final_price - initial_price) / initial_price
            annual_return = (1 + total_return) ** (1/10) - 1  # Retorno anualizado
            
            return {
                "current_price": final_price,
                "total_return_10y": total_return * 100,  # em percentual
                "annual_return": annual_return * 100,     # em percentual
            }
            
        except Exception as e:
            # Dados históricos como fallback
            return {
                "current_price": 4500.0,  # Valor aproximado
                "total_return_10y": 150.0,  # Retorno aproximado de 10 anos
                "annual_return": self.sp500_historical_return * 100
            }

    def get_stock_info(self, symbol: str) -> Dict:
        """Obtém informações sobre ações usando yfinance"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            return {
                "current_price": info.get("currentPrice"),
                "dividend_yield": info.get("dividendYield"),
                "fifty_day_average": info.get("fiftyDayAverage")
            }
        except Exception as e:
            return {"error": str(e)}

    def calculate_mortgage_savings(self, 
                                 loan_amount: float,
                                 interest_rate: float,
                                 extra_payment: float) -> Dict:
        """Calcula a economia potencial em um empréstimo habitação"""
        monthly_rate = interest_rate / 12 / 100
        total_interest_saved = extra_payment * interest_rate / 100
        years_reduced = extra_payment / (loan_amount * monthly_rate)
        
        return {
            "total_interest_saved": total_interest_saved,
            "years_reduced": years_reduced
        }

    def analyze_investment_options(self, amount: float) -> str:
        """Analisa diferentes opções de investimento com dados atualizados"""
        options = []
        
        # Obtém taxas Euribor atuais
        euribor_rates = self.get_euribor_rates()
        
        # Obtém performance do S&P 500
        sp500_data = self.get_sp500_performance()
        
        # Análise de certificados do tesouro (usando Euribor 12m + 1% como aproximação)
        treasury_rate = euribor_rates['12 months'] + 1.0
        treasury_return = amount * (treasury_rate / 100)
        options.append(f"Certificados do Tesouro (taxa atual: {treasury_rate:.2f}%): €{treasury_return:.2f}/ano")
        
        # Análise de investimento em ações (usando dados S&P 500)
        expected_stock_return = amount * (sp500_data['annual_return'] / 100)
        options.append(
            f"Investimento em S&P 500 (retorno médio anual: {sp500_data['annual_return']:.2f}%): "
            f"€{expected_stock_return:.2f}/ano (estimativa baseada em dados históricos)"
        )
        
        # Análise de amortização de crédito habitação
        mortgage_rate = euribor_rates['6 months'] + 1.5  # Spread típico de 1.5%
        mortgage_savings = amount * (mortgage_rate / 100)
        options.append(
            f"Amortização de Crédito Habitação (taxa atual: {mortgage_rate:.2f}%): "
            f"€{mortgage_savings:.2f}/ano em juros poupados"
        )
        
        return "\n".join(options)

    def get_response(self, user_input: str) -> str:
        """Processa a entrada do usuário e retorna uma resposta"""
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # Prompt base para o GPT
        system_prompt = """
        É um consultor financeiro especializado. O cliente poderá fazer perguntas mais gerais sobre a sua situação financeira e pedir aconselhamento geral. Também poderá pedir ajuda para questões 
        mais especóificas como qual seria a poupança em juros no caso de uma amortização de um crédito à habitação ou crédito pessoal. Tanto nos casos mais específicos como mais gerias antes de uma resposta final 
        deverão ser feitas questões sobre os parâmetros utilizados para os cálculos como se utiliza taxa variável ou fixa, se existe algum spread, se utilzia o modelo frânces, etc.. As respostas devem ser completas e contemplar
        a poupança no caso de a amortização ter efeito na prestação mensal ou no prazo de pagamento. Também poderâm ser feitas comparações entre investir o dinheiro em ações, obrigações, ou etfs e a amortização.
        Os dados deverão ir sendo guardados para que o modelo possa ir aprendendo com as respostas dadas e melhorar a qualidade das respostas.
        No caso de perguntas da vida financeira geral da pessoa as questões ao utilizador sobre parâmetros como valores que tem como reserva devem ser feitas de forma indirecta e não de forma directa. Pode ser aconselhado o valor ideial 
        para ter em reserva por exemplo ou para ter na conta corrente ou num eventuial fundo de oportunidade. Estes valores devem ser calculados tendo em conta dados do utilziador. 
        Deve ser utilziado portugês de Portugal.

        """
        
        try:
            client = openai.Client()  # Corrige a criação do cliente

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},  # Corrige o papel da mensagem
                    *self.conversation_history
                ]
            )

            bot_response = response.choices[0].message.content  # Correção aqui
            self.conversation_history.append({"role": "assistant", "content": bot_response})
            return bot_response

        except Exception as e:
            return f"Desculpe, ocorreu um erro: {str(e)}"

def main():
    try:
        bot = FinanceBot()
        print("Bem-vindo ao Consultor Financeiro! (Digite 'sair' para terminar)")
        
        while True:
            user_input = input("\nVocê: ")
            if user_input.lower() == 'sair':
                break
                
            response = bot.get_response(user_input)
            print(f"\nConsultor: {response}")
            
    except ValueError as e:
        print(f"Erro de configuração: {e}")
        print("Por favor, configure suas variáveis de ambiente no arquivo .env")

if __name__ == "__main__":
    main()
